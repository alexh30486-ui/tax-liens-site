variable "use_localstack" {
  description = "If true, AWS resources are provisioned against LocalStack (free, local) instead of real AWS."
  type        = bool
  default     = true
}

variable "aws_access_key" {
  description = "Only used when use_localstack = false."
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_secret_key" {
  description = "Only used when use_localstack = false."
  type        = string
  default     = ""
  sensitive   = true
}

variable "fly_org" {
  description = "Your Fly.io organization slug (find with `fly orgs list`)."
  type        = string
}

variable "fly_app_name" {
  description = "Globally unique Fly.io app name for the API."
  type        = string
  default     = "tax-lien-finder-api"
}

variable "fly_region" {
  description = "Fly.io region code."
  type        = string
  default     = "ord" # Chicago — low-latency to most US counties' data
}
