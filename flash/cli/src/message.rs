//! Stable JSON boundary used by the WebAssembly build.

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::protocol::{FRAME_VERSION, Frame, ProtocolError};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct JsonMessage {
    pub version: u8,
    pub channel: u8,
    pub opcode: u8,
    pub sequence: u8,
    pub payload: Vec<u8>,
}

impl TryFrom<JsonMessage> for Frame {
    type Error = MessageError;

    fn try_from(message: JsonMessage) -> Result<Self, Self::Error> {
        if message.version != FRAME_VERSION {
            return Err(MessageError::UnsupportedVersion(message.version));
        }
        Ok(Frame::new(
            message.channel.try_into()?,
            message.opcode,
            message.sequence,
            message.payload,
        )?)
    }
}

impl From<Frame> for JsonMessage {
    fn from(frame: Frame) -> Self {
        Self {
            version: FRAME_VERSION,
            channel: frame.channel as u8,
            opcode: frame.opcode,
            sequence: frame.sequence,
            payload: frame.payload,
        }
    }
}

pub fn encode_message_json(message: &str) -> Result<Vec<u8>, MessageError> {
    let message: JsonMessage = serde_json::from_str(message)?;
    Ok(Frame::try_from(message)?.encode())
}

pub fn decode_message_json(wire: &[u8]) -> Result<String, MessageError> {
    let message = JsonMessage::from(Frame::decode(wire)?);
    Ok(serde_json::to_string(&message)?)
}

#[derive(Debug, Error)]
pub enum MessageError {
    #[error("invalid message JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("unsupported frame version {0}")]
    UnsupportedVersion(u8),
    #[error(transparent)]
    Protocol(#[from] ProtocolError),
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{BootCommand, Channel};

    #[test]
    fn json_and_wire_round_trip() {
        let message = JsonMessage {
            version: FRAME_VERSION,
            channel: Channel::Boot as u8,
            opcode: BootCommand::SelectImage as u8,
            sequence: 17,
            payload: vec![3],
        };
        let json = serde_json::to_string(&message).unwrap();
        let wire = encode_message_json(&json).unwrap();
        assert_eq!(
            serde_json::from_str::<JsonMessage>(&decode_message_json(&wire).unwrap()).unwrap(),
            message
        );
    }

    #[test]
    fn json_boundary_validates_version_and_fields() {
        assert!(matches!(
            encode_message_json(
                r#"{"version":2,"channel":1,"opcode":0,"sequence":0,"payload":[]}"#
            ),
            Err(MessageError::UnsupportedVersion(2))
        ));
        assert!(
            encode_message_json(
                r#"{"version":1,"channel":1,"opcode":0,"sequence":0,"payload":[],"extra":0}"#
            )
            .is_err()
        );
    }
}
