# Load inventory file
locals {
  # Try to load inventory file, use empty map if not found
  inventory_file = try("${path.module}/${var.inventory_file}", var.inventory_file)
  inventory_vars = try({
    for line in split("\n", file(local.inventory_file)) :
    split("=", line)[0] => try(split("=", line)[1], "")
    if length(split("=", line)) == 2 && !startswith(trimspace(line), "#") && trimspace(line) != ""
  }, {})
  
  vps1_host = try(local.inventory_vars["VPS1_HOST"], "")
  vps2_host = try(local.inventory_vars["VPS2_HOST"], "")
  vps3_host = try(local.inventory_vars["VPS3_HOST"], "")
  
  vps1_ssh_user = try(local.inventory_vars["VPS1_SSH_USER"], "root")
  vps2_ssh_user = try(local.inventory_vars["VPS2_SSH_USER"], "root")
  vps3_ssh_user = try(local.inventory_vars["VPS3_SSH_USER"], "root")
  
  vps1_ssh_port = try(local.inventory_vars["VPS1_SSH_PORT"], "22")
  vps2_ssh_port = try(local.inventory_vars["VPS2_SSH_PORT"], "22")
  vps3_ssh_port = try(local.inventory_vars["VPS3_SSH_PORT"], "22")
  
  dry_run_flag = var.dry_run ? "--dry-run" : ""
}

# VPS1 (APP) - Prerequisites
resource "null_resource" "vps1_prereqs" {
  triggers = {
    host = local.vps1_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/00_prereqs.sh \
        --host ${local.vps1_host} \
        --user ${local.vps1_ssh_user} \
        --port ${local.vps1_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS1 (APP) - WireGuard
resource "null_resource" "vps1_wireguard" {
  depends_on = [null_resource.vps1_prereqs]

  triggers = {
    host = local.vps1_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/10_wireguard.sh \
        --host ${local.vps1_host} \
        --user ${local.vps1_ssh_user} \
        --port ${local.vps1_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS1 (APP) - Firewall
resource "null_resource" "vps1_firewall" {
  depends_on = [null_resource.vps1_wireguard]

  triggers = {
    host = local.vps1_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/20_firewall.sh \
        --host ${local.vps1_host} \
        --user ${local.vps1_ssh_user} \
        --port ${local.vps1_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS2 (DATA) - Prerequisites
resource "null_resource" "vps2_prereqs" {
  triggers = {
    host = local.vps2_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/00_prereqs.sh \
        --host ${local.vps2_host} \
        --user ${local.vps2_ssh_user} \
        --port ${local.vps2_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS2 (DATA) - WireGuard
resource "null_resource" "vps2_wireguard" {
  depends_on = [null_resource.vps2_prereqs]

  triggers = {
    host = local.vps2_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/10_wireguard.sh \
        --host ${local.vps2_host} \
        --user ${local.vps2_ssh_user} \
        --port ${local.vps2_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS2 (DATA) - Firewall
resource "null_resource" "vps2_firewall" {
  depends_on = [null_resource.vps2_wireguard]

  triggers = {
    host = local.vps2_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/20_firewall.sh \
        --host ${local.vps2_host} \
        --user ${local.vps2_ssh_user} \
        --port ${local.vps2_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS3 (WORKER) - Prerequisites
resource "null_resource" "vps3_prereqs" {
  triggers = {
    host = local.vps3_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/00_prereqs.sh \
        --host ${local.vps3_host} \
        --user ${local.vps3_ssh_user} \
        --port ${local.vps3_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS3 (WORKER) - WireGuard
resource "null_resource" "vps3_wireguard" {
  depends_on = [null_resource.vps3_prereqs]

  triggers = {
    host = local.vps3_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/10_wireguard.sh \
        --host ${local.vps3_host} \
        --user ${local.vps3_ssh_user} \
        --port ${local.vps3_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

# VPS3 (WORKER) - Firewall
resource "null_resource" "vps3_firewall" {
  depends_on = [null_resource.vps3_wireguard]

  triggers = {
    host = local.vps3_host
  }

  provisioner "local-exec" {
    command = <<-EOT
      export SSH_PRIVATE_KEY="${var.ssh_private_key}"
      export INVENTORY_FILE="${local.inventory_file}"
      ${var.scripts_dir}/bootstrap/20_firewall.sh \
        --host ${local.vps3_host} \
        --user ${local.vps3_ssh_user} \
        --port ${local.vps3_ssh_port} \
        ${local.dry_run_flag}
    EOT
  }
}

