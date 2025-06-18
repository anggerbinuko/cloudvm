// GCP Terraform Variables

variable "credentials_json" {
  description = "GCP credentials JSON"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"  # Default zone jika tidak ditentukan
}

variable "name" {
  description = "Name of the VM instance"
  type        = string
}

variable "machine_type" {
  description = "Machine type for the VM instance"
  type        = string
  default     = "e2-micro"
}

variable "image" {
  description = "Image for the VM instance"
  type        = string
  default     = "debian-cloud/debian-12-bookworm"
}

variable "disk_size" {
  description = "Size of the boot disk in GB"
  type        = number
  default     = 10
}

variable "public_ip" {
  description = "Apakah VM harus memiliki IP publik"
  type        = bool
  default     = true
}

variable "preset" {
  description = "Preset VM yang digunakan (low_cost, web_server, app_server)"
  type        = string
  default     = "low_cost"
}
