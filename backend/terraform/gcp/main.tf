// GCP Terraform Configuration

# Main Terraform file untuk GCP VM deployment
# Menggunakan preset templates berdasarkan parameter yang dipilih user

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  credentials = var.credentials_json
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

# Aktifkan OS Login di level project
resource "google_compute_project_metadata" "default" {
  metadata = {
    enable-oslogin = "TRUE"
  }
}

# Gunakan resource langsung daripada module dengan source yang dinamis

# VM Low Cost (e2-micro)
resource "google_compute_instance" "low_cost_vm" {
  count        = var.preset == "low_cost" ? 1 : 0
  name         = var.name
  machine_type = "e2-micro"
  zone         = var.zone

  boot_disk {
    auto_delete = true
    device_name = var.name

    initialize_params {
      image = "projects/debian-cloud/global/images/debian-12-bookworm-v20250415"
      size  = var.disk_size
      type  = "pd-balanced"
    }

    mode = "READ_WRITE"
  }

  can_ip_forward      = false
  deletion_protection = false
  enable_display      = false

  labels = {
    goog-ec-src           = "cloud-vm-platform"
    goog-ops-agent-policy = "v2-x86-template-1-4-0"
    vm_type               = "low_cost"
  }

  network_interface {
    dynamic "access_config" {
      for_each = var.public_ip ? [1] : []
      content {
        network_tier = "PREMIUM"
      }
    }

    subnetwork = "projects/${var.project_id}/regions/${substr(var.zone, 0, length(var.zone)-2)}/subnetworks/default"
  }

  scheduling {
    automatic_restart   = false
    on_host_maintenance = "TERMINATE"
    preemptible         = true
    provisioning_model  = "SPOT"
  }

  service_account {
    email  = "default"
    scopes = ["https://www.googleapis.com/auth/devstorage.read_only", 
              "https://www.googleapis.com/auth/logging.write", 
              "https://www.googleapis.com/auth/monitoring.write", 
              "https://www.googleapis.com/auth/service.management.readonly", 
              "https://www.googleapis.com/auth/servicecontrol", 
              "https://www.googleapis.com/auth/trace.append"]
  }

  tags = ["http-server", "https-server"]
}

# VM Web Server (e2-medium)
resource "google_compute_instance" "web_server_vm" {
  count        = var.preset == "web_server" ? 1 : 0
  name         = var.name
  machine_type = "e2-medium"
  zone         = var.zone

  boot_disk {
    auto_delete = true
    device_name = var.name

    initialize_params {
      image = "projects/debian-cloud/global/images/debian-12-bookworm-v20250415"
      size  = var.disk_size
      type  = "pd-balanced"
    }

    mode = "READ_WRITE"
  }

  can_ip_forward      = false
  deletion_protection = false
  enable_display      = false

  labels = {
    goog-ec-src           = "cloud-vm-platform"
    vm_type               = "web_server"
  }

  network_interface {
    dynamic "access_config" {
      for_each = var.public_ip ? [1] : []
      content {
        network_tier = "PREMIUM"
      }
    }

    subnetwork = "projects/${var.project_id}/regions/${substr(var.zone, 0, length(var.zone)-2)}/subnetworks/default"
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    provisioning_model  = "STANDARD"
  }

  service_account {
    email  = "default"
    scopes = ["https://www.googleapis.com/auth/devstorage.read_only", 
              "https://www.googleapis.com/auth/logging.write", 
              "https://www.googleapis.com/auth/monitoring.write", 
              "https://www.googleapis.com/auth/service.management.readonly", 
              "https://www.googleapis.com/auth/servicecontrol", 
              "https://www.googleapis.com/auth/trace.append"]
  }

  tags = ["http-server", "https-server", "web-server"]
}

# VM App Server (n2-standard-2)
resource "google_compute_instance" "app_server_vm" {
  count        = var.preset == "app_server" ? 1 : 0
  name         = var.name
  machine_type = "n2-standard-2"
  zone         = var.zone

  boot_disk {
    auto_delete = true
    device_name = var.name

    initialize_params {
      image = "projects/debian-cloud/global/images/debian-12-bookworm-v20250415"
      size  = var.disk_size
      type  = "pd-ssd" # SSD untuk performa lebih baik
    }

    mode = "READ_WRITE"
  }

  can_ip_forward      = false
  deletion_protection = false
  enable_display      = false

  labels = {
    goog-ec-src           = "cloud-vm-platform"
    vm_type               = "app_server"
  }

  network_interface {
    dynamic "access_config" {
      for_each = var.public_ip ? [1] : []
      content {
        network_tier = "PREMIUM"
      }
    }

    subnetwork = "projects/${var.project_id}/regions/${substr(var.zone, 0, length(var.zone)-2)}/subnetworks/default"
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    provisioning_model  = "STANDARD"
  }

  service_account {
    email  = "default"
    scopes = ["https://www.googleapis.com/auth/devstorage.read_only", 
              "https://www.googleapis.com/auth/logging.write", 
              "https://www.googleapis.com/auth/monitoring.write", 
              "https://www.googleapis.com/auth/service.management.readonly", 
              "https://www.googleapis.com/auth/servicecontrol", 
              "https://www.googleapis.com/auth/trace.append"]
  }

  tags = ["http-server", "https-server", "app-server"]
}

# Output tunggal yang menangani semua jenis VM
output "vm_name" {
  value = var.preset == "low_cost" ? (length(google_compute_instance.low_cost_vm) > 0 ? google_compute_instance.low_cost_vm[0].name : "") : (
           var.preset == "web_server" ? (length(google_compute_instance.web_server_vm) > 0 ? google_compute_instance.web_server_vm[0].name : "") : (
             length(google_compute_instance.app_server_vm) > 0 ? google_compute_instance.app_server_vm[0].name : ""))
}

output "internal_ip" {
  value = var.preset == "low_cost" ? (length(google_compute_instance.low_cost_vm) > 0 ? google_compute_instance.low_cost_vm[0].network_interface[0].network_ip : "") : (
           var.preset == "web_server" ? (length(google_compute_instance.web_server_vm) > 0 ? google_compute_instance.web_server_vm[0].network_interface[0].network_ip : "") : (
             length(google_compute_instance.app_server_vm) > 0 ? google_compute_instance.app_server_vm[0].network_interface[0].network_ip : ""))
}

output "external_ip" {
  value = var.public_ip ? (
           var.preset == "low_cost" ? (length(google_compute_instance.low_cost_vm) > 0 ? google_compute_instance.low_cost_vm[0].network_interface[0].access_config[0].nat_ip : "") : (
             var.preset == "web_server" ? (length(google_compute_instance.web_server_vm) > 0 ? google_compute_instance.web_server_vm[0].network_interface[0].access_config[0].nat_ip : "") : (
               length(google_compute_instance.app_server_vm) > 0 ? google_compute_instance.app_server_vm[0].network_interface[0].access_config[0].nat_ip : "")
           )
         ) : "VM ini tidak memiliki IP publik"
}

# Informasi tambahan untuk debugging
output "deployment_timestamp" {
  value = timestamp()
}
