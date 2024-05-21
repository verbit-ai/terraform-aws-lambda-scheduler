variable "schedule_expression" {
  default     = "cron(5 * * * ? *)"
  description = "the aws cloudwatch event rule scheule expression that specifies when the scheduler runs. Default is 5 minuts past the hour. for debugging use 'rate(5 minutes)'. See https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html"
}

variable "tag" {
  default     = "schedule"
  description = "the tag name used on the EC2 or RDS instance to contain the schedule json string for the instance."
}

variable "permissions_boundary" {
  type 		  = string
  default 	  = ""
  description = "AWS IAM Permissions Boundary ARN to be attached to the IAM Role"
}

variable "exclude" {
  default     = ""
  description = "common separated list of EC2 and RDS instance ids to exclude from scheduling."
}

variable "ec2_schedule" {
  default     = "{\"mon\": {\"start\": 6, \"stop\": 19},\"tue\": {\"start\": 6, \"stop\": 19},\"wed\": {\"start\": 6, \"stop\": 19},\"thu\": {\"start\": 6, \"stop\": 19}, \"fri\": {\"start\": 6, \"stop\": 19}}"
  description = "the default schedule tag containing json schedule information to add to instance when schedule_tag_force set to true."
}

variable "rds_schedule" {
  default     = "{\"mon\": {\"start\": 5, \"stop\": 19},\"tue\": {\"start\": 5, \"stop\": 19},\"wed\": {\"start\": 5, \"stop\": 19},\"thu\": {\"start\": 5, \"stop\": 19}, \"fri\": {\"start\": 5, \"stop\": 19}}"
  description = "the default schedule tag containing json schedule information to add to instance when schedule_tag_force set to true."
}

variable "debugmode" {
  default = "False"
  description = "set to true to enable debug mode. This will log the schedule json to cloudwatch logs."
}

variable "time" {
  default     = "America/Denver"
  description = "timezone to use for scheduler. Can be 'local', 'gmt' or an Olson timezone from https://gist.github.com/ykessler/3349954. default is 'gmt'. local time is for the AWS region."
}

variable "ec2_scheduling_enabled" {
  type        = string
  default     = "true"
  description = "Whether to do scheduling for EC2 instances."
}

variable "rds_scheduling_enabled" {
  type        = string
  default     = "true"
  description = "Whether to do scheduling for RDS instances."
}

variable "security_group_ids" {
  type        = list(string)
  default     = []
  description = "list of the vpc security groups to run lambda scheduler in."
}

variable "subnet_ids" {
  type        = list(string)
  default     = []
  description = "list of subnet_ids that the scheduler runs in."
}

variable "resource_name_prefix" {
  default     = ""
  description = "a prefix to apply to resource names created by this module."
}
