#!/bin/bash
cd "$(dirname "$1/_")"
echo "installing go modules"
go mod tidy
echo "install completed"
echo "running main.go"
go run /Users/nabhansuwanachote/Desktop/code/iac-research-ast-go/main_iac_research.go -directoryPath "$1"  -outputPath "$2"