use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant};

use clap::{Parser, Subcommand, ValueEnum};
use nextmicon_flash::client::{ClientError, DeviceClient};
use nextmicon_flash::protocol::Image;
use nextmicon_flash::serial::{BoardInfo, DeviceManager, SerialError, UsbId};
use thiserror::Error;

#[derive(Debug, Parser)]
#[command(
    name = "nmb",
    version,
    about = "NextMicon FPGA programmer and image manager"
)]
struct Cli {
    /// Restrict discovery to a hexadecimal VID:PID. May be repeated.
    #[arg(long = "usb-id", value_name = "VID:PID", global = true)]
    usb_ids: Vec<UsbId>,

    /// Timeout for one framed serial request.
    #[arg(
        long,
        value_name = "MILLISECONDS",
        default_value_t = 30_000,
        value_parser = clap::value_parser!(u64).range(1..),
        global = true
    )]
    timeout_ms: u64,

    /// Time to wait for the boot image to re-enumerate before flashing.
    #[arg(
        long,
        value_name = "SECONDS",
        default_value_t = 15,
        value_parser = clap::value_parser!(u64).range(1..),
        global = true
    )]
    reenumeration_timeout: u64,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// List connected NextMicon boards.
    Ls {
        /// Include USB identity and current image role.
        #[arg(short, long)]
        verbose: bool,
    },
    /// Warm-boot the protected boot image or the user image.
    Boot {
        /// Board name reported by `nmb ls`.
        board: String,
        /// Image role to start.
        image: ImageRole,
    },
    /// Erase, program, manifest, and verify the user image.
    Flash {
        /// Board name reported by `nmb ls`.
        board: String,
        /// Raw iCE40 bitstream to program.
        #[arg(value_name = "BITSTREAM")]
        image: PathBuf,
        /// Boot the newly programmed image after verification.
        #[arg(long)]
        boot: bool,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum ImageRole {
    Boot,
    User,
}

impl ImageRole {
    const fn image(self) -> Image {
        match self {
            Self::Boot => Image::Boot,
            Self::User => Image::User,
        }
    }

    const fn label(self) -> &'static str {
        match self {
            Self::Boot => "boot",
            Self::User => "user",
        }
    }
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("nmb: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run(cli: Cli) -> Result<(), AppError> {
    let manager = DeviceManager::new(cli.usb_ids);
    let timeout = Duration::from_millis(cli.timeout_ms);

    match cli.command {
        Command::Ls { verbose } => list_boards(&manager, verbose),
        Command::Boot { board, image } => {
            let board = manager.find(&board)?;
            let transport = manager.open(&board, timeout)?;
            let mut client = DeviceClient::new(transport, timeout);
            client.boot(image.image())?;
            println!("{} accepted boot to {}", board.name, image.label());
            Ok(())
        }
        Command::Flash { board, image, boot } => {
            let data = read_image(&image)?;
            let mut board = manager.find(&board)?;

            let active_image = {
                let transport = manager.open(&board, timeout)?;
                let mut client = DeviceClient::new(transport, timeout);
                client.info()?.active_image
            };
            if !active_image.is_boot() {
                eprintln!("Switching {} to the boot image...", board.name);
                {
                    let transport = manager.open(&board, timeout)?;
                    let mut client = DeviceClient::new(transport, timeout);
                    client.boot(Image::Boot)?;
                }
                board = wait_for_image(
                    &manager,
                    &board,
                    Image::Boot,
                    Duration::from_secs(cli.reenumeration_timeout),
                )?;
            }

            eprintln!(
                "Programming {} bytes into {} user image and verifying readback...",
                data.len(),
                board.name
            );
            let transport = manager.open(&board, timeout)?;
            let mut client = DeviceClient::new(transport, timeout);
            let manifest = client.program_user_image(&data)?;
            println!(
                "Programmed {}/user: {} bytes, CRC32 {:08x}, verified",
                board.name, manifest.image_length, manifest.crc32
            );
            if boot {
                client.boot(Image::User)?;
                println!("{} accepted boot to user", board.name);
            }
            Ok(())
        }
    }
}

fn list_boards(manager: &DeviceManager, verbose: bool) -> Result<(), AppError> {
    for board in manager.list()? {
        if verbose {
            let product = board.product.as_deref().unwrap_or("unknown product");
            let active_image = manager
                .open(&board, Duration::from_millis(250))
                .ok()
                .and_then(|transport| {
                    DeviceClient::new(transport, Duration::from_millis(250))
                        .info()
                        .ok()
                })
                .map(|info| match info.active_image {
                    Image::Boot => "boot".to_owned(),
                    Image::User => "user".to_owned(),
                })
                .unwrap_or_else(|| "unknown".to_owned());
            println!(
                "{}\t{}\t{}\t{}\t{}",
                board.name, active_image, board.usb_id, board.port_name, product
            );
        } else {
            println!("{}", board.name);
        }
    }
    Ok(())
}

fn read_image(path: &Path) -> Result<Vec<u8>, AppError> {
    std::fs::read(path).map_err(|source| AppError::ReadImage {
        path: path.to_owned(),
        source,
    })
}

fn wait_for_image(
    manager: &DeviceManager,
    original: &BoardInfo,
    target: Image,
    timeout: Duration,
) -> Result<BoardInfo, AppError> {
    let deadline = Instant::now() + timeout;
    loop {
        let boards = manager.list()?;
        let candidates: Vec<_> = boards
            .iter()
            .filter(|board| original.same_board_as(board))
            .cloned()
            .collect();
        let candidates = if original.serial.is_none() && candidates.is_empty() && boards.len() == 1
        {
            boards
        } else {
            candidates
        };
        for board in candidates {
            let probe_timeout = Duration::from_millis(250);
            if let Ok(transport) = manager.open(&board, probe_timeout) {
                let mut client = DeviceClient::new(transport, probe_timeout);
                if client.info().is_ok_and(|info| info.active_image == target) {
                    return Ok(board);
                }
            }
        }
        if Instant::now() >= deadline {
            return Err(AppError::ReenumerationTimeout {
                board: original.name.clone(),
                timeout,
            });
        }
        thread::sleep(Duration::from_millis(100));
    }
}

#[derive(Debug, Error)]
enum AppError {
    #[error(transparent)]
    Serial(#[from] SerialError),
    #[error(transparent)]
    Client(#[from] ClientError),
    #[error("could not read image {path:?}: {source}")]
    ReadImage {
        path: PathBuf,
        source: std::io::Error,
    },
    #[error("timed out after {timeout:?} waiting for {board:?} to re-enumerate as boot")]
    ReenumerationTimeout { board: String, timeout: Duration },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_named_boot_roles_and_unique_flash_target() {
        let cli = Cli::try_parse_from(["nmb", "boot", "cherry-0123", "user"]).unwrap();
        assert!(matches!(
            cli.command,
            Command::Boot {
                board,
                image: ImageRole::User
            } if board == "cherry-0123"
        ));

        let cli = Cli::try_parse_from(["nmb", "flash", "cherry-0123", "user.bin"]).unwrap();
        assert!(matches!(
            cli.command,
            Command::Flash { board, image, .. }
                if board == "cherry-0123" && image == PathBuf::from("user.bin")
        ));
        assert!(Cli::try_parse_from(["nmb", "boot", "cherry-0123", "2"]).is_err());
    }
}
