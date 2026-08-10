use crate::protocol::{IMAGE_SLOT_SIZE, Image, crc32};
use thiserror::Error;

pub const MANIFEST_MAGIC: [u8; 4] = *b"NMF1";
pub const MANIFEST_VERSION: u8 = 1;
pub const MANIFEST_SIZE: usize = 32;
pub const MAX_IMAGE_SIZE: usize = IMAGE_SLOT_SIZE as usize - MANIFEST_SIZE;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ImageManifest {
    pub image: Image,
    pub image_length: u32,
    pub crc32: u32,
}

impl ImageManifest {
    pub fn for_data(image: Image, data: &[u8]) -> Result<Self, ManifestError> {
        if data.is_empty() {
            return Err(ManifestError::EmptyImage);
        }
        if data.len() > MAX_IMAGE_SIZE {
            return Err(ManifestError::ImageTooLarge {
                actual: data.len(),
                maximum: MAX_IMAGE_SIZE,
            });
        }
        Ok(Self {
            image,
            image_length: data.len() as u32,
            crc32: crc32(data),
        })
    }

    pub fn address(self) -> u32 {
        self.image.flash_end() - MANIFEST_SIZE as u32
    }

    pub fn encode(self) -> [u8; MANIFEST_SIZE] {
        let mut bytes = [0xff; MANIFEST_SIZE];
        bytes[0..4].copy_from_slice(&MANIFEST_MAGIC);
        bytes[4] = MANIFEST_VERSION;
        bytes[5] = self.image as u8;
        bytes[6..8].copy_from_slice(&0u16.to_le_bytes());
        bytes[8..12].copy_from_slice(&self.image_length.to_le_bytes());
        bytes[12..16].copy_from_slice(&self.crc32.to_le_bytes());
        bytes
    }

    pub fn decode(bytes: &[u8]) -> Result<Self, ManifestError> {
        if bytes.len() != MANIFEST_SIZE {
            return Err(ManifestError::InvalidLength(bytes.len()));
        }
        if bytes[0..4] != MANIFEST_MAGIC {
            return Err(ManifestError::InvalidMagic);
        }
        if bytes[4] != MANIFEST_VERSION {
            return Err(ManifestError::UnsupportedVersion(bytes[4]));
        }
        let image = Image::try_from(bytes[5]).map_err(|_| ManifestError::InvalidImage(bytes[5]))?;
        let image_length = u32::from_le_bytes(bytes[8..12].try_into().unwrap());
        if image_length == 0 || image_length as usize > MAX_IMAGE_SIZE {
            return Err(ManifestError::InvalidImageLength(image_length));
        }
        let crc32 = u32::from_le_bytes(bytes[12..16].try_into().unwrap());
        Ok(Self {
            image,
            image_length,
            crc32,
        })
    }
}

#[derive(Debug, Error, Eq, PartialEq)]
pub enum ManifestError {
    #[error("image is empty")]
    EmptyImage,
    #[error("image is {actual} bytes; slot permits at most {maximum} bytes")]
    ImageTooLarge { actual: usize, maximum: usize },
    #[error("manifest must be {MANIFEST_SIZE} bytes, got {0}")]
    InvalidLength(usize),
    #[error("invalid manifest magic")]
    InvalidMagic,
    #[error("unsupported manifest version {0}")]
    UnsupportedVersion(u8),
    #[error("invalid manifest image {0}")]
    InvalidImage(u8),
    #[error("invalid manifest image length {0}")]
    InvalidImageLength(u32),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manifest_round_trip() {
        let data = b"fpga bitstream";
        let manifest = ImageManifest::for_data(Image::Image2, data).unwrap();
        assert_eq!(manifest.image_length, data.len() as u32);
        assert_eq!(manifest.address(), Image::Image2.flash_end() - 32);
        assert_eq!(ImageManifest::decode(&manifest.encode()), Ok(manifest));
    }

    #[test]
    fn invalid_image_sizes_are_rejected() {
        assert_eq!(
            ImageManifest::for_data(Image::Image1, &[]),
            Err(ManifestError::EmptyImage)
        );
        let oversized = vec![0; MAX_IMAGE_SIZE + 1];
        assert!(matches!(
            ImageManifest::for_data(Image::Image1, &oversized),
            Err(ManifestError::ImageTooLarge { .. })
        ));
    }
}
