//! Host-side constants shared with the FPGA USB endpoint policy.

pub const USB_MAX_PACKET_SIZE: u16 = 64;
pub const USB_DIRECTION_IN: u8 = 0x80;

pub const IMAGE_SLOT_SIZE: u32 = 0x04_0000;
pub const USER_DATA_BASE: u32 = 0x10_0000;
pub const FLASH_END: u32 = 0x40_0000;
pub const BOOT_REQUEST_SIZE: usize = 1;
pub const BOOT_RESPONSE_SIZE: usize = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Endpoint {
    Boot = 1,
    Flash = 2,
    Uart = 3,
}

impl Endpoint {
    pub const fn out_address(self) -> u8 {
        self as u8
    }

    pub const fn in_address(self) -> u8 {
        self as u8 | USB_DIRECTION_IN
    }

    pub const fn enabled_in(self, image: Image) -> bool {
        match self {
            Self::Boot => true,
            Self::Flash => image.is_bootloader(),
            Self::Uart => !image.is_bootloader(),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Image {
    Image0 = 0,
    Image1 = 1,
    Image2 = 2,
    Image3 = 3,
}

impl Image {
    pub const ALL: [Self; 4] = [Self::Image0, Self::Image1, Self::Image2, Self::Image3];

    pub const fn is_bootloader(self) -> bool {
        matches!(self, Self::Image0)
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
            0 => Ok(Self::Image0),
            1 => Ok(Self::Image1),
            2 => Ok(Self::Image2),
            3 => Ok(Self::Image3),
            _ => Err(InvalidImage(value)),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidImage(pub u8);

/// The one-byte payload sent to EP1 OUT.
///
/// EP1 identifies the BOOT service, so no command opcode is needed.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BootRequest {
    pub image: Image,
}

impl BootRequest {
    pub const fn encode(self) -> [u8; BOOT_REQUEST_SIZE] {
        [self.image as u8]
    }

    pub fn decode(packet: &[u8]) -> Result<Self, BootRequestError> {
        let [image] = packet else {
            return Err(BootRequestError::InvalidLength(packet.len()));
        };

        Image::try_from(*image)
            .map(|image| Self { image })
            .map_err(BootRequestError::InvalidImage)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BootRequestError {
    InvalidLength(usize),
    InvalidImage(InvalidImage),
}

/// The one-byte status returned on EP1 IN before an accepted warm boot starts.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum BootStatus {
    Accepted = 0x00,
    InvalidImage = 0x01,
    InvalidManifest = 0x02,
    Busy = 0x03,
}

impl BootStatus {
    pub const fn encode(self) -> [u8; BOOT_RESPONSE_SIZE] {
        [self as u8]
    }
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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidBootStatus(pub u8);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn endpoint_addresses_are_separate() {
        assert_eq!(Endpoint::Boot.out_address(), 0x01);
        assert_eq!(Endpoint::Boot.in_address(), 0x81);
        assert_eq!(Endpoint::Flash.out_address(), 0x02);
        assert_eq!(Endpoint::Flash.in_address(), 0x82);
        assert_eq!(Endpoint::Uart.out_address(), 0x03);
        assert_eq!(Endpoint::Uart.in_address(), 0x83);
    }

    #[test]
    fn endpoint_policy_matches_the_image_role() {
        for image in Image::ALL {
            assert!(Endpoint::Boot.enabled_in(image));
            assert_eq!(Endpoint::Flash.enabled_in(image), image == Image::Image0);
            assert_eq!(Endpoint::Uart.enabled_in(image), image != Image::Image0);
        }
    }

    #[test]
    fn image_slots_are_aligned_and_non_overlapping() {
        for (index, image) in Image::ALL.into_iter().enumerate() {
            assert_eq!(image.flash_base(), index as u32 * IMAGE_SLOT_SIZE);
            assert_eq!(image.flash_end(), (index as u32 + 1) * IMAGE_SLOT_SIZE);
        }
        assert_eq!(Image::Image3.flash_end(), USER_DATA_BASE);
        assert!(USER_DATA_BASE < FLASH_END);
    }

    #[test]
    fn image_number_validation_is_strict() {
        for value in 0..=3 {
            assert_eq!(Image::try_from(value).unwrap() as u8, value);
        }
        assert_eq!(Image::try_from(4), Err(InvalidImage(4)));
        assert_eq!(Image::try_from(u8::MAX), Err(InvalidImage(u8::MAX)));
    }

    #[test]
    fn boot_request_is_a_strict_one_byte_image_number() {
        for image in Image::ALL {
            let encoded = BootRequest { image }.encode();
            assert_eq!(BootRequest::decode(&encoded), Ok(BootRequest { image }));
        }

        assert_eq!(
            BootRequest::decode(&[]),
            Err(BootRequestError::InvalidLength(0))
        );
        assert_eq!(
            BootRequest::decode(&[0, 1]),
            Err(BootRequestError::InvalidLength(2))
        );
        assert_eq!(
            BootRequest::decode(&[4]),
            Err(BootRequestError::InvalidImage(InvalidImage(4)))
        );
    }

    #[test]
    fn boot_status_values_are_stable() {
        for (value, status) in [
            BootStatus::Accepted,
            BootStatus::InvalidImage,
            BootStatus::InvalidManifest,
            BootStatus::Busy,
        ]
        .into_iter()
        .enumerate()
        {
            assert_eq!(status.encode(), [value as u8]);
            assert_eq!(BootStatus::try_from(value as u8), Ok(status));
        }
        assert_eq!(BootStatus::try_from(4), Err(InvalidBootStatus(4)));
    }
}
