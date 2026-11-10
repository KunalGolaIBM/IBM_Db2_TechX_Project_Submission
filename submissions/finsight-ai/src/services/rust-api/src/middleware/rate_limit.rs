use axum::http::HeaderMap;
use std::{
    collections::HashMap,
    net::{IpAddr, Ipv4Addr},
    sync::Arc,
    time::{Duration, Instant},
};
use tokio::sync::Mutex;

#[derive(Clone)]
pub struct RateLimiter {
    state: Arc<Mutex<HashMap<IpAddr, (u32, Instant)>>>,
    max_tokens: u32,
    refill_duration: Duration,
}

impl RateLimiter {
    pub fn new(max_tokens: u32, refill_duration: Duration) -> Self {
        Self {
            state: Arc::new(Mutex::new(HashMap::new())),
            max_tokens,
            refill_duration,
        }
    }

    pub async fn check(&self, ip: IpAddr) -> bool {
        let mut map = self.state.lock().await;
        let now = Instant::now();

        if map.len() > 5000 {
            map.retain(|_, (_, last_refill)| now.duration_since(*last_refill) < Duration::from_secs(300));
        }

        let entry = map.entry(ip).or_insert((self.max_tokens, now));

        let elapsed = now.duration_since(entry.1);
        if elapsed >= self.refill_duration {
            entry.0 = self.max_tokens;
            entry.1 = now;
        }

        if entry.0 > 0 {
            entry.0 -= 1;
            true
        } else {
            false
        }
    }
}

pub fn extract_client_ip_from_headers(headers: &HeaderMap) -> IpAddr {
    if let Some(forwarded) = headers.get("x-forwarded-for") {
        if let Ok(s) = forwarded.to_str() {
            if let Some(first) = s.split(',').next() {
                if let Ok(ip) = first.trim().parse::<IpAddr>() {
                    return ip;
                }
            }
        }
    }

    if let Some(real_ip) = headers.get("x-real-ip") {
        if let Ok(s) = real_ip.to_str() {
            if let Ok(ip) = s.trim().parse::<IpAddr>() {
                return ip;
            }
        }
    }

    IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1))
}
