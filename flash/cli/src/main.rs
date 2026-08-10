use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::str::FromStr;
use std::thread;
use std::time::{Duration, Instant};

use clap::{Parser, Subcommand};
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

    /// Time to wait for image 0 to re-enumerate before flashing.
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
    /// Warm-boot one of the four FPGA images.
    Boot {
        /// Board and image in the form BOARD/0-3.
        target: BoardImageTarget,
    },
    /// Erase, program, manifest, and verify a user image slot.
    Flash {
        /// Board and destination in the form BOARD/1-3.
        target: BoardImageTarget,
        /// Raw iCE40 bitstream to program.
        image: PathBuf,
        /// Boot the newly programmed image after verification.
        #[arg(long)]
        boot: bool,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct BoardImageTarget {
    board: String,
    image: Image,
}

impl FromStr for BoardImageTarget {
    type Err = TargetError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let Some((board, image)) = value.rsplit_once('/') else {
            return Err(TargetError(value.to_owned()));
        };
        if board.is_empty() {
            return Err(TargetError(value.to_owned()));
        }
        let image = image
            .parse::<u8>()
            .ok()
            .and_then(|image| Image::try_from(image).ok())
            .ok_or_else(|| TargetError(value.to_owned()))?;
        Ok(Self {
            board: board.to_owned(),
            image,
        })
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
        Command::Boot { target } => {
            let board = manager.find(&target.board)?;
            let transport = manager.open(&board, timeout)?;
            let mut client = DeviceClient::new(transport, timeout);
            client.boot(target.image)?;
            println!(
                "{} accepted boot to image {}",
                board.name, target.image as u8
            );
            Ok(())
        }
        Command::Flash {
            target,
            image,
            boot,
        } => {
            if target.image.is_bootloader() {
                return Err(AppError::ProtectedImage);
            }
            let data = read_image(&image)?;
            let mut board = manager.find(&target.board)?;

            let active_image = {
                let transport = manager.open(&board, timeout)?;
                let mut client = DeviceClient::new(transport, timeout);
                client.info()?.active_image
            };
            if !active_image.is_bootloader() {
                eprintln!("Switching {} to image 0...", board.name);
                {
                    let transport = manager.open(&board, timeout)?;
                    let mut client = DeviceClient::new(transport, timeout);
                    client.boot(Image::Image0)?;
                }
                board = wait_for_image(
                    &manager,
                    &board,
                    Image::Image0,
                    Duration::from_secs(cli.reenumeration_timeout),
                )?;
            }

            eprintln!(
                "Programming {} bytes into {}/{} and verifying readback...",
                data.len(),
                board.name,
                target.image as u8
            );
            let transport = manager.open(&board, timeout)?;
            let mut client = DeviceClient::new(transport, timeout);
            let manifest = client.program_image(target.image, &data)?;
            println!(
                "Programmed {}/{}: {} bytes, CRC32 {:08x}, verified",
                board.name, target.image as u8, manifest.image_length, manifest.crc32
            );
            if boot {
                client.boot(target.image)?;
                println!(
                    "{} accepted boot to image {}",
                    board.name, target.image as u8
                );
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
                .map(|info| format!("image {}", info.active_image as u8))
                .unwrap_or_else(|| "image unknown".to_owned());
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

#[derive(Clone, Debug, Error, Eq, PartialEq)]
#[error("target must be BOARD/0-3, got {0:?}")]
struct TargetError(String);

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
    #[error(
        "image 0 is protected and cannot be written over USB; use the external SPI recovery procedure"
    )]
    ProtectedImage,
    #[error("timed out after {timeout:?} waiting for {board:?} to re-enumerate as image 0")]
    ReenumerationTimeout { board: String, timeout: Duration },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_board_image_targets() {
        assert_eq!(
            "cherry-0123/2".parse(),
            Ok(BoardImageTarget {
                board: "cherry-0123".to_owned(),
                image: Image::Image2,
            })
        );
        assert!("cherry-0123".parse::<BoardImageTarget>().is_err());
        assert!("cherry-0123/4".parse::<BoardImageTarget>().is_err());
        assert!("/1".parse::<BoardImageTarget>().is_err());
    }
}
