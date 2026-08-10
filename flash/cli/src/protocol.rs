//! CDC ACM framing and commands shared with the FPGA implementation.

use thiserror::Error;

pub const CDC_BAUD_RATE: u32 = 115_200;

pub const IMAGE_SLOT_SIZE: u32 = 0x04_0000;
pub const USER_DATA_BASE: u32 = 0x08_0000;
pub const FLASH_END: u32 = 0x40_0000;

pub const FRAME_VERSION: u8 = 1;
pub const FRAME_DELIMITER: u8 = 0;
pub const FRAME_HEADER_SIZE: usize = 6;
pub const FRAME_CRC_SIZE: usize = 4;
pub const FRAME_MAX_PAYLOAD_SIZE: usize = 256;
pub const FRAME_MAX_DECODED_SIZE: usize =
    FRAME_HEADER_SIZE + FRAME_MAX_PAYLOAD_SIZE + FRAME_CRC_SIZE;
// COBS adds one code byte per 254 decoded bytes, plus the trailing delimiter.
pub const FRAME_MAX_WIRE_SIZE: usize = 269;
pub const RESPONSE_BIT: u8 = 0x80;

pub const FLASH_ADDRESS_SIZE: usize = 3;
pub const FLASH_WRITE_DATA_SIZE: usize = FRAME_MAX_PAYLOAD_SIZE - FLASH_ADDRESS_SIZE;
pub const FLASH_READ_DATA_SIZE: usize = FRAME_MAX_PAYLOAD_SIZE - 1;

pub const CAPABILITY_BOOT: u8 = 1 << 0;
pub const CAPABILITY_FLASH: u8 = 1 << 1;
pub const CAPABILITY_UART: u8 = 1 << 2;

pub fn crc32(bytes: &[u8]) -> u32 {
    crc32fast::hash(bytes)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Channel {
    Boot = 0x01,
    Flash = 0x02,
    Uart = 0x03,
}

impl TryFrom<u8> for Channel {
    type Error = ProtocolError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x01 => Ok(Self::Boot),
            0x02 => Ok(Self::Flash),
            0x03 => Ok(Self::Uart),
            _ => Err(ProtocolError::InvalidChannel(value)),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum BootCommand {
    GetInfo = 0x00,
    SelectImage = 0x01,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum FlashCommand {
    EraseSlot = 0x01,
    Write = 0x02,
    Read = 0x03,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum UartCommand {
    Data = 0x01,
}

pub const fn response_opcode(command: u8) -> u8 {
    command | RESPONSE_BIT
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Frame {
    pub channel: Channel,
    pub opcode: u8,
    pub sequence: u8,
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn new(
        channel: Channel,
        opcode: u8,
        sequence: u8,
        payload: Vec<u8>,
    ) -> Result<Self, ProtocolError> {
        if payload.len() > FRAME_MAX_PAYLOAD_SIZE {
            return Err(ProtocolError::PayloadTooLarge(payload.len()));
        }
        Ok(Self {
            channel,
            opcode,
            sequence,
            payload,
        })
    }

    pub fn encode(&self) -> Vec<u8> {
        let mut decoded =
            Vec::with_capacity(FRAME_HEADER_SIZE + self.payload.len() + FRAME_CRC_SIZE);
        decoded.push(FRAME_VERSION);
        decoded.push(self.channel as u8);
        decoded.push(self.opcode);
        decoded.push(self.sequence);
        decoded.extend_from_slice(&(self.payload.len() as u16).to_le_bytes());
        decoded.extend_from_slice(&self.payload);
        decoded.extend_from_slice(&crc32(&decoded).to_le_bytes());

        let mut wire = cobs::encode_vec(&decoded);
        wire.push(FRAME_DELIMITER);
        wire
    }

    pub fn decode(wire: &[u8]) -> Result<Self, ProtocolError> {
        let encoded = wire.strip_suffix(&[FRAME_DELIMITER]).unwrap_or(wire);
        if encoded.is_empty() {
            return Err(ProtocolError::EmptyFrame);
        }
        if encoded.len() >= FRAME_MAX_WIRE_SIZE {
            return Err(ProtocolError::FrameTooLarge(encoded.len()));
        }
        let decoded = cobs::decode_vec(encoded).map_err(|_| ProtocolError::InvalidCobs)?;
        if decoded.len() < FRAME_HEADER_SIZE + FRAME_CRC_SIZE {
            return Err(ProtocolError::FrameTooShort(decoded.len()));
        }

        let payload_length = u16::from_le_bytes([decoded[4], decoded[5]]) as usize;
        if payload_length > FRAME_MAX_PAYLOAD_SIZE {
            return Err(ProtocolError::PayloadTooLarge(payload_length));
        }
        let expected_length = FRAME_HEADER_SIZE + payload_length + FRAME_CRC_SIZE;
        if decoded.len() != expected_length {
            return Err(ProtocolError::LengthMismatch {
                declared: payload_length,
                actual: decoded.len() - FRAME_HEADER_SIZE - FRAME_CRC_SIZE,
            });
        }

        let crc_offset = decoded.len() - FRAME_CRC_SIZE;
        let expected_crc = u32::from_le_bytes(decoded[crc_offset..].try_into().unwrap());
        let actual_crc = crc32(&decoded[..crc_offset]);
        if actual_crc != expected_crc {
            return Err(ProtocolError::CrcMismatch {
                expected: expected_crc,
                actual: actual_crc,
            });
        }
        if decoded[0] != FRAME_VERSION {
            return Err(ProtocolError::UnsupportedVersion(decoded[0]));
        }

        Ok(Self {
            channel: Channel::try_from(decoded[1])?,
            opcode: decoded[2],
            sequence: decoded[3],
            payload: decoded[FRAME_HEADER_SIZE..crc_offset].to_vec(),
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Image {
    Boot = 0,
    User = 1,
}

impl Image {
    pub const ALL: [Self; 2] = [Self::Boot, Self::User];

    pub const fn is_boot(self) -> bool {
        matches!(self, Self::Boot)
    }

    pub const fn flash_base(self) -> u32 {
        self as u32 * IMAGE_SLOT_SIZE
    }

    pub const fn flash_end(self) -> u32 {
        self.flash_base() + IMAGE_SLOT_SIZE
    }
}

impl TryFrom<u8> for Image {
    type Error = InvalidImage;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::Boot),
            1 => Ok(Self::User),
            _ => Err(InvalidImage(value)),
        }
    }
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
#[error("invalid image number {0}")]
pub struct InvalidImage(pub u8);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum BootStatus {
    Accepted = 0x00,
    InvalidImage = 0x01,
    InvalidManifest = 0x02,
    Busy = 0x03,
}

impl TryFrom<u8> for BootStatus {
    type Error = InvalidBootStatus;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x00 => Ok(Self::Accepted),
            0x01 => Ok(Self::InvalidImage),
            0x02 => Ok(Self::InvalidManifest),
            0x03 => Ok(Self::Busy),
            _ => Err(InvalidBootStatus(value)),
        }
    }
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
#[error("invalid BOOT status byte 0x{0:02x}")]
pub struct InvalidBootStatus(pub u8);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum FlashStatus {
    Accepted = 0x00,
    InvalidCommand = 0x01,
    InvalidAddress = 0x02,
    WriteProtected = 0x03,
    Busy = 0x04,
    IoError = 0x05,
}

impl TryFrom<u8> for FlashStatus {
    type Error = InvalidFlashStatus;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x00 => Ok(Self::Accepted),
            0x01 => Ok(Self::InvalidCommand),
            0x02 => Ok(Self::InvalidAddress),
            0x03 => Ok(Self::WriteProtected),
            0x04 => Ok(Self::Busy),
            0x05 => Ok(Self::IoError),
            _ => Err(InvalidFlashStatus(value)),
        }
    }
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
#[error("invalid FLASH status byte 0x{0:02x}")]
pub struct InvalidFlashStatus(pub u8);

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
pub enum FlashRequestError {
    #[error("invalid FLASH length {0}")]
    InvalidLength(usize),
    #[error("invalid FLASH address 0x{0:06x}")]
    InvalidAddress(u32),
}

pub fn encode_erase_slot() -> [u8; 1] {
    [Image::User as u8]
}

pub fn encode_flash_write(address: u32, data: &[u8]) -> Result<Vec<u8>, FlashRequestError> {
    if data.is_empty() || data.len() > FLASH_WRITE_DATA_SIZE {
        return Err(FlashRequestError::InvalidLength(data.len()));
    }
    validate_flash_range(address, data.len())?;

    let mut payload = Vec::with_capacity(FLASH_ADDRESS_SIZE + data.len());
    payload.extend_from_slice(&encode_address(address));
    payload.extend_from_slice(data);
    Ok(payload)
}

pub fn encode_flash_read(address: u32, length: usize) -> Result<[u8; 5], FlashRequestError> {
    if length == 0 || length > FLASH_READ_DATA_SIZE {
        return Err(FlashRequestError::InvalidLength(length));
    }
    validate_flash_range(address, length)?;

    let encoded = encode_address(address);
    let length = (length as u16).to_le_bytes();
    Ok([encoded[0], encoded[1], encoded[2], length[0], length[1]])
}

pub const fn decode_address(bytes: [u8; FLASH_ADDRESS_SIZE]) -> u32 {
    u32::from_le_bytes([bytes[0], bytes[1], bytes[2], 0])
}

const fn encode_address(address: u32) -> [u8; FLASH_ADDRESS_SIZE] {
    let bytes = address.to_le_bytes();
    [bytes[0], bytes[1], bytes[2]]
}

fn validate_flash_range(address: u32, length: usize) -> Result<(), FlashRequestError> {
    let Some(end) = address.checked_add(length as u32) else {
        return Err(FlashRequestError::InvalidAddress(address));
    };
    if end > FLASH_END {
        return Err(FlashRequestError::InvalidAddress(address));
    }
    Ok(())
}

#[derive(Debug, Error, Eq, PartialEq)]
pub enum ProtocolError {
    #[error("frame is empty")]
    EmptyFrame,
    #[error("frame is too short: {0} decoded bytes")]
    FrameTooShort(usize),
    #[error("frame is too large: {0} encoded bytes")]
    FrameTooLarge(usize),
    #[error("COBS decoding failed")]
    InvalidCobs,
    #[error("unsupported frame version {0}")]
    UnsupportedVersion(u8),
    #[error("invalid channel 0x{0:02x}")]
    InvalidChannel(u8),
    #[error("payload is too large: {0} bytes")]
    PayloadTooLarge(usize),
    #[error("payload length mismatch: header says {declared}, frame contains {actual}")]
    LengthMismatch { declared: usize, actual: usize },
    #[error("frame CRC mismatch: expected {expected:08x}, calculated {actual:08x}")]
    CrcMismatch { expected: u32, actual: u32 },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frame_round_trip_handles_zeroes_and_maximum_payload() {
        let payload: Vec<_> = (0..=255).map(|value| value as u8).collect();
        let frame = Frame::new(Channel::Flash, FlashCommand::Write as u8, 42, payload).unwrap();
        let wire = frame.encode();
        assert!(wire.len() <= FRAME_MAX_WIRE_SIZE);
        assert_eq!(wire.last(), Some(&FRAME_DELIMITER));
        assert!(!wire[..wire.len() - 1].contains(&FRAME_DELIMITER));
        assert_eq!(Frame::decode(&wire), Ok(frame));
    }

    #[test]
    fn frame_rejects_corruption_and_wrong_lengths() {
        let frame = Frame::new(Channel::Boot, BootCommand::SelectImage as u8, 7, vec![1]).unwrap();
        let mut wire = frame.encode();
        wire[3] ^= 0x40;
        assert!(Frame::decode(&wire).is_err());

        assert_eq!(
            Frame::new(Channel::Uart, UartCommand::Data as u8, 0, vec![0; 257]),
            Err(ProtocolError::PayloadTooLarge(257))
        );
    }

    #[test]
    fn response_opcodes_are_separate() {
        assert_eq!(response_opcode(BootCommand::GetInfo as u8), 0x80);
        assert_eq!(response_opcode(BootCommand::SelectImage as u8), 0x81);
        assert_eq!(response_opcode(FlashCommand::Read as u8), 0x83);
    }

    #[test]
    fn image_slots_are_aligned_and_non_overlapping() {
        for (index, image) in Image::ALL.into_iter().enumerate() {
            assert_eq!(image.flash_base(), index as u32 * IMAGE_SLOT_SIZE);
            assert_eq!(image.flash_end(), (index as u32 + 1) * IMAGE_SLOT_SIZE);
        }
        assert_eq!(Image::User.flash_end(), USER_DATA_BASE);
        const { assert!(USER_DATA_BASE < FLASH_END) };
    }

    #[test]
    fn flash_payload_limits_match_the_frame_limit() {
        let data = [0xa5; FLASH_WRITE_DATA_SIZE];
        let write = encode_flash_write(Image::User.flash_base(), &data).unwrap();
        assert_eq!(write.len(), FRAME_MAX_PAYLOAD_SIZE);
        assert_eq!(decode_address([write[0], write[1], write[2]]), 0x04_0000);
        assert_eq!(&write[3..], data);

        let read = encode_flash_read(FLASH_END - FLASH_READ_DATA_SIZE as u32, 255).unwrap();
        assert_eq!(read, [0x01, 0xff, 0x3f, 0xff, 0x00]);
    }

    #[test]
    fn flash_payload_validation_is_strict() {
        assert_eq!(
            encode_flash_write(0, &[]),
            Err(FlashRequestError::InvalidLength(0))
        );
        assert_eq!(
            encode_flash_read(0, FLASH_READ_DATA_SIZE + 1),
            Err(FlashRequestError::InvalidLength(256))
        );
        assert_eq!(
            encode_flash_read(FLASH_END, 1),
            Err(FlashRequestError::InvalidAddress(FLASH_END))
        );
    }
}
