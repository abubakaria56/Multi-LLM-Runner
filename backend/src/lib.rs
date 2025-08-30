use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

pub const PROTO_VER: u16 = 1;

pub type TimestampMs = i64;

#[cfg(feature = "jsonschema")]
use schemars::JsonSchema;

/* ======================= Account / Snapshot ======================= */
#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(rename_all = "snake_case")]
pub struct AccountInfo {
    pub login: Option<u64>, // 0/None if not logged in
    pub name: Option<String>,
    pub server: Option<String>,
    pub currency: Option<String>,

    pub balance: Option<f64>,
    pub equity: Option<f64>,
    pub margin: Option<f64>,
    pub margin_free: Option<f64>,
    pub margin_level: Option<f64>, // %
    pub leverage: Option<u32>,

    pub trade_allowed: Option<bool>,
    pub trade_mode: Option<u8>,
    pub ping_ms: Option<u32>,

    pub connected: Option<bool>,
    pub logged_in: Option<bool>,

    pub ts_millis: TimestampMs, // EA-side timestamp when sampled
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(rename_all = "snake_case")]
pub struct EaSnapshot {
    pub pid: Option<u32>,
    pub build: Option<u32>,

    pub account: Option<String>,
    pub server: Option<String>,
    pub connected: Option<bool>,
    pub trade_allowed: Option<bool>,
    pub algo_trading_enabled: Option<bool>,

    pub account_info: Option<AccountInfo>, // NEW: rich account state
    pub config_digest: Option<String>,     // EA reports what it sees
}

/* ======================= Config ======================= */

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(rename_all = "snake_case")]
pub struct ConfigDoc {
    pub version: u64, // monotonically increasing
    /// "ini" | "json" (free-form string to keep it flexible)
    pub format: String,
    /// Serialized config body as written to disk.
    pub body: String,
}

/* ======================= Control ======================= */

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(rename_all = "snake_case")]
pub enum ControlAction {
    Continue,
    Stop,
    Restart,
}

/* ======================= Login ======================= */

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
pub struct LoginCreds {
    pub server: String,
    pub login_number: String,
    pub password: String, // delivered over secure Core channel
    pub broker_name: Option<String>,
    pub master_password: Option<String>,
}

/* ======================= Core wire messages ======================= */

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(tag = "type", rename_all = "snake_case", content = "data")]
pub enum ToCore {
    /// Ask Core to provide credentials for this instance.
    RequestLogin { instance_id: Uuid, run_id: Uuid },

    /// Ask Core to HMAC-sign a nonce (Sidecar never holds the token).
    RequestHmac {
        instance_id: Uuid,
        run_id: Uuid,
        nonce_b64: String,
    },

    /// Emitted after MT5 process starts (good for UI + DB runs table).
    ProcessStarted {
        instance_id: Uuid,
        run_id: Uuid,
        pid: u32,
        ts: TimestampMs,
    },

    /// Emitted when MT5 exits (clean or crash).
    ProcessExited {
        instance_id: Uuid,
        run_id: Uuid,
        exit_code: Option<i32>,
        ts: TimestampMs,
        reason: Option<String>,
    },

    /// Result of handshake (parsed/validated by Sidecar).
    HandshakeResult {
        instance_id: Uuid,
        run_id: Uuid,
        ts: TimestampMs,
        ok: bool,
        proto: u32,
        build: Option<u32>,
        account: Option<String>,
        server: Option<String>,
        error: Option<String>,
    },

    /// Regular heartbeat with EA snapshot.
    Heartbeat {
        instance_id: Uuid,
        run_id: Uuid,
        ts: TimestampMs,
        snapshot: EaSnapshot,
    },

    /// Optional health downgrade notification (missed N heartbeats).
    Degraded {
        instance_id: Uuid,
        run_id: Uuid,
        ts: TimestampMs,
        missed: u32,
        reason: Option<String>,
    },

    /// Free-form telemetry / log forwarding if we want to surface it in Core.
    /// Structured event for audits/ops (free-form payload).
    Event {
        instance_id: Uuid,
        run_id: Uuid,
        kind: String,
        ts: TimestampMs,
        payload: Value,
    },

    /// Lightweight metrics/counters.
    Metric {
        instance_id: Uuid,
        run_id: Uuid,
        name: String,
        value: f64,
        ts: TimestampMs,
    },

    /// Sidecar logs surfaced to Core.
    Log {
        instance_id: Uuid,
        run_id: Uuid,
        level: String,
        ts: TimestampMs,
        msg: String,
    },

    // Login Status
    LoginStatus {
        instance_id: Uuid,
        ok: bool,
        details: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "jsonschema", derive(JsonSchema))]
#[serde(tag = "type", rename_all = "snake_case", content = "data")]
pub enum FromCore {
    /// Core responds with credentials.
    ProvideLogin { creds: LoginCreds },

    /// Core replies with HMAC for the provided nonce.
    Hmac {
        instance_id: Uuid,
        run_id: Uuid,
        nonce_b64: String,
        hmac_b64: String,
    },

    /// Push a new configuration document (Sidecar writes atomically).
    ConfigUpdate { doc: ConfigDoc },

    /// Ask Sidecar/EA to apply the last config (soft reload / flag).
    ApplyConfig,

    /// Control plane directives (stop / restart / etc).
    Control {
        action: ControlAction,
        reason: Option<String>,
        backoff_ms: Option<u32>,
    },

    /// Explicit restart request with human-readable reason.
    RestartInstance { reason: String },

    /// Generic acknowledgement (keep for simple RPC acks).
    Ack,
}
