variable "inventory_file" {
  description = "Path to inventory file"
  type        = string
  default     = "inventory/hosts.env"
}

variable "ssh_private_key" {
  description = "SSH private key for VPS access"
  type        = string
  sensitive   = true
  default     = ""
}

variable "scripts_dir" {
  description = "Directory containing bootstrap scripts"
  type        = string
  default     = "../scripts"
}

variable "dry_run" {
  description = "Run in dry-run mode (no actual changes)"
  type        = bool
  default     = false
}


