use std::time::Duration;

use thiserror::Error;

use crate::manifest::{ImageManifest, ManifestError};
use crate::protocol::{
    BootCommand, BootStatus, CAPABILITY_BOOT, Channel, FLASH_READ_DATA_SIZE, FLASH_WRITE_DATA_SIZE,
    FlashCommand, FlashRequestError, FlashStatus, Frame, Image, InvalidBootStatus,
    InvalidFlashStatus, ProtocolError, encode_erase_slot, encode_flash_read, encode_flash_write,
};

pub trait FrameTransport {
    fn exchange(&mut self, request: &Frame, timeout: Duration) -> Result<Frame, TransportError>;
}

#[derive(Debug, Error)]
#[error("{0}")]
pub struct TransportError(pub String);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DeviceInfo {
    pub active_image: Image,
    pub capabilities: u8,
}

pub struct DeviceClient<T> {
    transport: T,
    timeout: Duration,
    next_sequence: u8,
}

impl<T: FrameTransport> DeviceClient<T> {
    pub fn new(transport: T, timeout: Duration) -> Self {
        Self {
            transport,
            timeout,
            next_sequence: 0,
        }
    }

    pub fn info(&mut self) -> Result<DeviceInfo, ClientError> {
        let response = self.request(Channel::Boot, BootCommand::GetInfo as u8, Vec::new())?;
        if response.len() != 3 {
            return Err(ClientError::ResponseLength {
                operation: "BOOT GET_INFO",
                expected: 3,
                actual: response.len(),
            });
        }
        self.check_boot_status(response[0])?;
        let active_image = Image::try_from(response[1])?;
        if response[2] & CAPABILITY_BOOT == 0 {
            return Err(ClientError::InvalidCapabilities(response[2]));
        }
        Ok(DeviceInfo {
            active_image,
            capabilities: response[2],
        })
    }

    pub fn boot(&mut self, image: Image) -> Result<(), ClientError> {
        let response = self.request(
            Channel::Boot,
            BootCommand::SelectImage as u8,
            vec![image as u8],
        )?;
        if response.len() != 1 {
            return Err(ClientError::ResponseLength {
                operation: "BOOT SELECT_IMAGE",
                expected: 1,
                actual: response.len(),
            });
        }
        self.check_boot_status(response[0])
    }

    /// Erases, writes, manifests, and reads back the single user image.
    ///
    /// The boot image is intentionally inaccessible through this API. Factory
    /// recovery uses the external SPI header rather than normal USB flashing.
    pub fn program_user_image(&mut self, data: &[u8]) -> Result<ImageManifest, ClientError> {
        let image = Image::User;
        let manifest = ImageManifest::for_data(data)?;

        self.erase_user_image()?;
        self.write_at(image.flash_base(), data)?;
        self.write_at(manifest.address(), &manifest.encode())?;
        self.verify_at(image.flash_base(), data)?;
        self.verify_at(manifest.address(), &manifest.encode())?;
        Ok(manifest)
    }

    fn erase_user_image(&mut self) -> Result<(), ClientError> {
        self.flash_command(FlashCommand::EraseSlot, encode_erase_slot().to_vec())
    }

    fn write_at(&mut self, mut address: u32, mut data: &[u8]) -> Result<(), ClientError> {
        while !data.is_empty() {
            let length = data.len().min(FLASH_WRITE_DATA_SIZE);
            let payload = encode_flash_write(address, &data[..length])?;
            self.flash_command(FlashCommand::Write, payload)?;
            address += length as u32;
            data = &data[length..];
        }
        Ok(())
    }

    fn verify_at(&mut self, mut address: u32, mut expected: &[u8]) -> Result<(), ClientError> {
        while !expected.is_empty() {
            let length = expected.len().min(FLASH_READ_DATA_SIZE);
            let actual = self.read_at(address, length)?;
            if actual != expected[..length] {
                let offset = actual
                    .iter()
                    .zip(&expected[..length])
                    .position(|(actual, expected)| actual != expected)
                    .unwrap_or(0);
                return Err(ClientError::VerificationFailed {
                    address: address + offset as u32,
                    expected: expected[offset],
                    actual: actual[offset],
                });
            }
            address += length as u32;
            expected = &expected[length..];
        }
        Ok(())
    }

    fn read_at(&mut self, address: u32, length: usize) -> Result<Vec<u8>, ClientError> {
        let request = encode_flash_read(address, length)?;
        let response = self.request(Channel::Flash, FlashCommand::Read as u8, request.to_vec())?;
        if response.len() != length + 1 {
            return Err(ClientError::ResponseLength {
                operation: "FLASH READ",
                expected: length + 1,
                actual: response.len(),
            });
        }
        self.check_flash_status(response[0])?;
        Ok(response[1..].to_vec())
    }

    fn flash_command(
        &mut self,
        command: FlashCommand,
        payload: Vec<u8>,
    ) -> Result<(), ClientError> {
        let response = self.request(Channel::Flash, command as u8, payload)?;
        if response.len() != 1 {
            return Err(ClientError::ResponseLength {
                operation: "FLASH command",
                expected: 1,
                actual: response.len(),
            });
        }
        self.check_flash_status(response[0])
    }

    fn request(
        &mut self,
        channel: Channel,
        opcode: u8,
        payload: Vec<u8>,
    ) -> Result<Vec<u8>, ClientError> {
        let sequence = self.next_sequence;
        self.next_sequence = self.next_sequence.wrapping_add(1);
        let request = Frame::new(channel, opcode, sequence, payload)?;
        let response = self.transport.exchange(&request, self.timeout)?;
        Ok(response.payload)
    }

    fn check_boot_status(&self, value: u8) -> Result<(), ClientError> {
        let status = BootStatus::try_from(value)?;
        match status {
            BootStatus::Accepted => Ok(()),
            status => Err(ClientError::BootRejected(status)),
        }
    }

    fn check_flash_status(&self, value: u8) -> Result<(), ClientError> {
        let status = FlashStatus::try_from(value)?;
        match status {
            FlashStatus::Accepted => Ok(()),
            status => Err(ClientError::FlashRejected(status)),
        }
    }
}

#[derive(Debug, Error)]
pub enum ClientError {
    #[error(transparent)]
    Transport(#[from] TransportError),
    #[error(transparent)]
    Protocol(#[from] ProtocolError),
    #[error("{operation} response must be {expected} bytes, got {actual}")]
    ResponseLength {
        operation: &'static str,
        expected: usize,
        actual: usize,
    },
    #[error("BOOT request rejected: {0:?}")]
    BootRejected(BootStatus),
    #[error("FLASH request rejected: {0:?}")]
    FlashRejected(FlashStatus),
    #[error("device reported invalid capabilities 0x{0:02x}")]
    InvalidCapabilities(u8),
    #[error(
        "flash verification failed at 0x{address:06x}: expected 0x{expected:02x}, got 0x{actual:02x}"
    )]
    VerificationFailed {
        address: u32,
        expected: u8,
        actual: u8,
    },
    #[error(transparent)]
    InvalidImage(#[from] crate::protocol::InvalidImage),
    #[error(transparent)]
    BootStatus(#[from] InvalidBootStatus),
    #[error(transparent)]
    FlashStatus(#[from] InvalidFlashStatus),
    #[error(transparent)]
    FlashPacket(#[from] FlashRequestError),
    #[error(transparent)]
    Manifest(#[from] ManifestError),
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::manifest::MANIFEST_SIZE;
    use crate::protocol::{
        CAPABILITY_FLASH, CAPABILITY_UART, FLASH_END, decode_address, response_opcode,
    };

    struct FakeDevice {
        memory: Vec<u8>,
        active_image: Image,
        last_request: Option<Frame>,
    }

    impl FakeDevice {
        fn new(active_image: Image) -> Self {
            Self {
                memory: vec![0xff; FLASH_END as usize],
                active_image,
                last_request: None,
            }
        }

        fn response(request: &Frame, payload: Vec<u8>) -> Result<Frame, TransportError> {
            Frame::new(
                request.channel,
                response_opcode(request.opcode),
                request.sequence,
                payload,
            )
            .map_err(|error| TransportError(error.to_string()))
        }
    }

    impl FrameTransport for FakeDevice {
        fn exchange(
            &mut self,
            request: &Frame,
            _timeout: Duration,
        ) -> Result<Frame, TransportError> {
            self.last_request = Some(request.clone());
            match (request.channel, request.opcode) {
                (Channel::Boot, value) if value == BootCommand::GetInfo as u8 => {
                    let capabilities = CAPABILITY_BOOT
                        | if self.active_image.is_boot() {
                            CAPABILITY_FLASH
                        } else {
                            CAPABILITY_UART
                        };
                    Self::response(
                        request,
                        vec![
                            BootStatus::Accepted as u8,
                            self.active_image as u8,
                            capabilities,
                        ],
                    )
                }
                (Channel::Boot, value) if value == BootCommand::SelectImage as u8 => {
                    self.active_image = Image::try_from(request.payload[0]).unwrap();
                    Self::response(request, vec![BootStatus::Accepted as u8])
                }
                (Channel::Flash, value) if value == FlashCommand::EraseSlot as u8 => {
                    let image = Image::try_from(request.payload[0]).unwrap();
                    self.memory[image.flash_base() as usize..image.flash_end() as usize].fill(0xff);
                    Self::response(request, vec![FlashStatus::Accepted as u8])
                }
                (Channel::Flash, value) if value == FlashCommand::Write as u8 => {
                    let address = decode_address(request.payload[..3].try_into().unwrap()) as usize;
                    for (destination, source) in self.memory
                        [address..address + request.payload.len() - 3]
                        .iter_mut()
                        .zip(&request.payload[3..])
                    {
                        *destination &= *source;
                    }
                    Self::response(request, vec![FlashStatus::Accepted as u8])
                }
                (Channel::Flash, value) if value == FlashCommand::Read as u8 => {
                    let address = decode_address(request.payload[..3].try_into().unwrap()) as usize;
                    let length =
                        u16::from_le_bytes(request.payload[3..5].try_into().unwrap()) as usize;
                    let mut payload = Vec::with_capacity(length + 1);
                    payload.push(FlashStatus::Accepted as u8);
                    payload.extend_from_slice(&self.memory[address..address + length]);
                    Self::response(request, payload)
                }
                _ => Self::response(request, vec![FlashStatus::InvalidCommand as u8]),
            }
        }
    }

    #[test]
    fn reads_device_info_and_boots() {
        let mut client = DeviceClient::new(FakeDevice::new(Image::User), Duration::from_secs(1));
        assert_eq!(
            client.info().unwrap(),
            DeviceInfo {
                active_image: Image::User,
                capabilities: CAPABILITY_BOOT | CAPABILITY_UART,
            }
        );
        assert!(client.boot(Image::Boot).is_ok());
        assert_eq!(client.transport.active_image, Image::Boot);
        assert_eq!(client.transport.last_request.as_ref().unwrap().sequence, 1);
    }

    #[test]
    fn programs_and_verifies_user_image() {
        let data: Vec<u8> = (0..=255).cycle().take(600).collect();
        let mut client = DeviceClient::new(FakeDevice::new(Image::Boot), Duration::from_secs(1));
        let manifest = client.program_user_image(&data).unwrap();

        assert_eq!(manifest.image, Image::User);
        assert_eq!(manifest.image_length, 600);
        assert_eq!(manifest.crc32, crc32fast::hash(&data));
        assert_eq!(
            manifest.address(),
            Image::User.flash_end() - MANIFEST_SIZE as u32
        );
    }
}
