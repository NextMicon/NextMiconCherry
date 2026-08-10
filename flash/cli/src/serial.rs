use std::collections::VecDeque;
use std::fmt;
use std::io::{Read, Write};
use std::str::FromStr;
use std::time::{Duration, Instant};

use serialport::{ClearBuffer, SerialPort, SerialPortType};
use thiserror::Error;

use crate::client::{FrameTransport, TransportError};
use crate::protocol::{
    CDC_BAUD_RATE, FRAME_DELIMITER, FRAME_MAX_WIRE_SIZE, Frame, response_opcode,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UsbId {
    pub vendor_id: u16,
    pub product_id: u16,
}

impl FromStr for UsbId {
    type Err = UsbIdError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let Some((vendor, product)) = value.split_once(':') else {
            return Err(UsbIdError(value.to_owned()));
        };
        Ok(Self {
            vendor_id: parse_hex_u16(vendor).ok_or_else(|| UsbIdError(value.to_owned()))?,
            product_id: parse_hex_u16(product).ok_or_else(|| UsbIdError(value.to_owned()))?,
        })
    }
}

impl fmt::Display for UsbId {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:04x}:{:04x}", self.vendor_id, self.product_id)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BoardInfo {
    pub name: String,
    pub port_name: String,
    pub serial: Option<String>,
    pub manufacturer: Option<String>,
    pub product: Option<String>,
    pub usb_id: UsbId,
}

impl BoardInfo {
    pub fn same_board_as(&self, other: &Self) -> bool {
        match (&self.serial, &other.serial) {
            (Some(left), Some(right)) => left == right,
            _ => self.name == other.name,
        }
    }
}

pub struct DeviceManager {
    usb_ids: Vec<UsbId>,
}

impl DeviceManager {
    pub fn new(usb_ids: Vec<UsbId>) -> Self {
        Self { usb_ids }
    }

    pub fn list(&self) -> Result<Vec<BoardInfo>, SerialError> {
        let ports = serialport::available_ports().map_err(SerialError::EnumeratePorts)?;
        let mut boards = Vec::new();
        for port in ports {
            let SerialPortType::UsbPort(usb) = port.port_type else {
                continue;
            };
            let usb_id = UsbId {
                vendor_id: usb.vid,
                product_id: usb.pid,
            };
            if self.usb_ids.is_empty() {
                if !is_nextmicon(usb.manufacturer.as_deref(), usb.product.as_deref()) {
                    continue;
                }
            } else if !self.usb_ids.contains(&usb_id) {
                continue;
            }

            let serial = usb
                .serial_number
                .map(|value| sanitize_descriptor_string(&value))
                .filter(|value| !value.is_empty());
            let name = board_name(serial.as_deref(), usb_id, &port.port_name);
            boards.push(BoardInfo {
                name,
                port_name: port.port_name,
                serial,
                manufacturer: usb.manufacturer,
                product: usb.product,
                usb_id,
            });
        }
        boards.sort_by(|left, right| left.name.cmp(&right.name));
        Ok(boards)
    }

    pub fn find(&self, name: &str) -> Result<BoardInfo, SerialError> {
        let matches: Vec<_> = self
            .list()?
            .into_iter()
            .filter(|board| board.name == name)
            .collect();
        match matches.as_slice() {
            [] => Err(SerialError::BoardNotFound(name.to_owned())),
            [board] => Ok(board.clone()),
            _ => Err(SerialError::AmbiguousBoard(name.to_owned())),
        }
    }

    pub fn open(
        &self,
        board: &BoardInfo,
        timeout: Duration,
    ) -> Result<SerialFrameTransport, SerialError> {
        let port = serialport::new(&board.port_name, CDC_BAUD_RATE)
            .timeout(timeout)
            .open()
            .map_err(|source| SerialError::Open {
                board: board.name.clone(),
                port: board.port_name.clone(),
                source,
            })?;
        let _ = port.clear(ClearBuffer::All);
        Ok(SerialFrameTransport {
            port,
            pending: VecDeque::new(),
        })
    }
}

pub struct SerialFrameTransport {
    port: Box<dyn SerialPort>,
    pending: VecDeque<u8>,
}

impl SerialFrameTransport {
    pub fn send_frame(&mut self, frame: &Frame, timeout: Duration) -> Result<(), TransportError> {
        self.port
            .set_timeout(timeout)
            .map_err(|error| TransportError(format!("could not set serial timeout: {error}")))?;
        let wire = frame.encode();
        self.port
            .write_all(&wire)
            .map_err(|error| TransportError(format!("serial write failed: {error}")))?;
        self.port
            .flush()
            .map_err(|error| TransportError(format!("serial flush failed: {error}")))
    }

    pub fn receive_frame(&mut self, timeout: Duration) -> Result<Frame, TransportError> {
        let deadline = Instant::now() + timeout;
        loop {
            if let Some(delimiter) = self
                .pending
                .iter()
                .position(|value| *value == FRAME_DELIMITER)
            {
                let wire: Vec<_> = self.pending.drain(..=delimiter).collect();
                if wire.len() == 1 {
                    continue;
                }
                match Frame::decode(&wire) {
                    Ok(frame) => return Ok(frame),
                    Err(_) => continue,
                }
            }

            if self.pending.len() >= FRAME_MAX_WIRE_SIZE {
                self.pending.clear();
            }
            let now = Instant::now();
            if now >= deadline {
                return Err(TransportError(
                    "timed out waiting for a framed response".to_owned(),
                ));
            }
            self.port.set_timeout(deadline - now).map_err(|error| {
                TransportError(format!("could not set serial timeout: {error}"))
            })?;
            let mut buffer = [0u8; 256];
            match self.port.read(&mut buffer) {
                Ok(0) => continue,
                Ok(length) => self.pending.extend(&buffer[..length]),
                Err(error) if error.kind() == std::io::ErrorKind::TimedOut => {
                    return Err(TransportError(
                        "timed out waiting for a framed response".to_owned(),
                    ));
                }
                Err(error) => {
                    return Err(TransportError(format!("serial read failed: {error}")));
                }
            }
        }
    }
}

impl FrameTransport for SerialFrameTransport {
    fn exchange(&mut self, request: &Frame, timeout: Duration) -> Result<Frame, TransportError> {
        self.send_frame(request, timeout)?;
        let deadline = Instant::now() + timeout;
        loop {
            let now = Instant::now();
            if now >= deadline {
                return Err(TransportError(
                    "timed out waiting for a matching response".to_owned(),
                ));
            }
            let response = self.receive_frame(deadline - now)?;
            if response.channel == request.channel
                && response.sequence == request.sequence
                && response.opcode == response_opcode(request.opcode)
            {
                return Ok(response);
            }
            // UART or stale management frames may be present in the byte stream.
            // They cannot be mistaken for the matching response because channel,
            // opcode, and sequence are all checked.
        }
    }
}

#[derive(Debug, Error)]
pub enum SerialError {
    #[error("could not enumerate serial ports: {0}")]
    EnumeratePorts(serialport::Error),
    #[error("board {0:?} was not found; run `nmb ls`")]
    BoardNotFound(String),
    #[error("more than one board is named {0:?}; program unique USB serial numbers")]
    AmbiguousBoard(String),
    #[error("could not open {board:?} at {port:?}: {source}; check serial-port permissions")]
    Open {
        board: String,
        port: String,
        source: serialport::Error,
    },
}

#[derive(Clone, Debug, Error, Eq, PartialEq)]
#[error("USB ID must be hexadecimal VID:PID, got {0:?}")]
pub struct UsbIdError(pub String);

fn parse_hex_u16(value: &str) -> Option<u16> {
    u16::from_str_radix(value.strip_prefix("0x").unwrap_or(value), 16).ok()
}

fn is_nextmicon(manufacturer: Option<&str>, product: Option<&str>) -> bool {
    manufacturer.is_some_and(|value| value.eq_ignore_ascii_case("NextMicon"))
        || product.is_some_and(|value| value.to_ascii_lowercase().starts_with("nextmicon cherry"))
}

fn sanitize_descriptor_string(value: &str) -> String {
    value
        .trim_matches(|character: char| character.is_whitespace() || character == '\0')
        .to_owned()
}

fn board_name(serial: Option<&str>, usb_id: UsbId, port_name: &str) -> String {
    if let Some(serial) = serial {
        let serial: String = serial
            .chars()
            .map(|character| {
                if character.is_ascii_alphanumeric() || matches!(character, '-' | '_') {
                    character
                } else {
                    '-'
                }
            })
            .collect();
        if serial.to_ascii_lowercase().starts_with("cherry-") {
            return serial;
        }
        return format!("cherry-{serial}");
    }
    let port: String = port_name
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() {
                character
            } else {
                '-'
            }
        })
        .collect();
    format!("cherry-{usb_id}-{port}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_usb_ids() {
        assert_eq!(
            "1209:0001".parse(),
            Ok(UsbId {
                vendor_id: 0x1209,
                product_id: 1,
            })
        );
        assert_eq!(
            "0x1209:0x00ff".parse(),
            Ok(UsbId {
                vendor_id: 0x1209,
                product_id: 0x00ff,
            })
        );
        assert!("1209".parse::<UsbId>().is_err());
    }

    #[test]
    fn recognizes_descriptors_and_board_names() {
        assert!(is_nextmicon(Some("NextMicon"), None));
        assert!(is_nextmicon(None, Some("NextMicon Cherry Bootloader")));
        assert!(!is_nextmicon(Some("unrelated"), Some("serial")));
        let id = UsbId {
            vendor_id: 0x1209,
            product_id: 1,
        };
        assert_eq!(board_name(Some("0123"), id, "/dev/ttyACM0"), "cherry-0123");
        assert_eq!(
            board_name(Some("cherry-ab/cd"), id, "/dev/ttyACM0"),
            "cherry-ab-cd"
        );
        assert_eq!(
            board_name(None, id, "/dev/ttyACM0"),
            "cherry-1209:0001--dev-ttyACM0"
        );
    }
}
