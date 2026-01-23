output "vps1_wireguard_ip" {
  description = "WireGuard IP for VPS1 (APP)"
  value       = try(local.inventory_vars["VPS1_WIREGUARD_IP"], "10.10.0.1")
}

output "vps2_wireguard_ip" {
  description = "WireGuard IP for VPS2 (DATA)"
  value       = try(local.inventory_vars["VPS2_WIREGUARD_IP"], "10.10.0.2")
}

output "vps3_wireguard_ip" {
  description = "WireGuard IP for VPS3 (WORKER)"
  value       = try(local.inventory_vars["VPS3_WIREGUARD_IP"], "10.10.0.3")
}

output "vps1_host" {
  description = "VPS1 hostname/IP"
  value       = local.vps1_host
}

output "vps2_host" {
  description = "VPS2 hostname/IP"
  value       = local.vps2_host
}

output "vps3_host" {
  description = "VPS3 hostname/IP"
  value       = local.vps3_host
}

output "postgres_endpoint" {
  description = "PostgreSQL endpoint (via PgBouncer on VPS1)"
  value       = "127.0.0.1:6432"
}

output "redis_endpoint" {
  description = "Redis endpoint (on VPS2)"
  value       = "${try(local.inventory_vars["VPS2_WIREGUARD_IP"], "10.10.0.2")}:6379"
}


