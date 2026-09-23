package main

import (
	"flag"

	"sandbox_lifecycle_http/internal/lifecycle"
)

func main() {
	viewOnly := flag.Bool("view-only", false, "poll the saved async_task_id without submitting another command")
	flag.Parse()
	lifecycle.Main(func() error { return lifecycle.RunAsyncInvoke(*viewOnly) })
}
