"""Tests for scaffolder.parser."""
from scaffolder.parser import parse_response


_WELL_FORMED = """\
FILE: versions.tf
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
---
FILE: variables.tf
variable "region" {
  type    = string
  default = "us-east-1"
}
---
FILE: main.tf
provider "aws" {
  region = var.region
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name        = "main"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
---
FILE: outputs.tf
output "vpc_id" {
  value = aws_vpc.main.id
}
---"""

_NO_FILE_BLOCKS = """\
```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
```"""


class TestParseResponse:
    def test_well_formed_returns_all_files(self):
        files = parse_response(_WELL_FORMED)
        assert set(files.keys()) == {"versions.tf", "variables.tf", "main.tf", "outputs.tf"}

    def test_file_content_correct(self):
        files = parse_response(_WELL_FORMED)
        assert 'aws_vpc" "main"' in files["main.tf"]
        assert 'ManagedBy   = "terraform"' in files["main.tf"]

    def test_file_content_ends_with_newline(self):
        files = parse_response(_WELL_FORMED)
        for path, content in files.items():
            assert content.endswith("\n"), f"{path} does not end with newline"

    def test_fallback_no_file_blocks(self):
        files = parse_response(_NO_FILE_BLOCKS)
        assert "main.tf" in files
        assert "aws_vpc" in files["main.tf"]
        # Code fences should be stripped
        assert "```" not in files["main.tf"]

    def test_empty_response_fallback(self):
        files = parse_response("")
        assert "main.tf" in files

    def test_separator_stripped_from_content(self):
        files = parse_response(_WELL_FORMED)
        for content in files.values():
            assert not content.strip().endswith("---")
