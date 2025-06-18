// AWS Terraform Variables

variable "access_key" {
  description = "AWS Access Key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "AWS Secret Key"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Name for the VM instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "ami_id" {
  description = "AMI ID to use for the instance"
  type        = string
  default     = "ami-0c55b159cbfafe1f0" # Amazon Linux 2 AMI
}

variable "key_name" {
  description = "Key pair name to use for SSH access"
  type        = string
  default     = null
}

variable "security_group_ids" {
  description = "Security group IDs to attach to the instance"
  type        = list(string)
  default     = []
}

variable "storage_size" {
  description = "Size of root volume in GB"
  type        = number
  default     = 8
}

variable "environment" {
  description = "Environment tag for the instance"
  type        = string
  default     = "development"
}
