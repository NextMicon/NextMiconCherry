use wasm_bindgen::prelude::*;

#[wasm_bindgen(js_name = encodeMessageJson)]
pub fn encode_message_json(message: &str) -> Result<Vec<u8>, JsError> {
    crate::message::encode_message_json(message).map_err(|error| JsError::new(&error.to_string()))
}

#[wasm_bindgen(js_name = decodeMessageJson)]
pub fn decode_message_json(wire: &[u8]) -> Result<String, JsError> {
    crate::message::decode_message_json(wire).map_err(|error| JsError::new(&error.to_string()))
}

#[wasm_bindgen(js_name = crc32)]
pub fn crc32(bytes: &[u8]) -> u32 {
    crate::protocol::crc32(bytes)
}
