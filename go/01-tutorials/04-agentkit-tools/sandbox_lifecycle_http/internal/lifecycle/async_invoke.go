package lifecycle

import (
	"fmt"
	"os"
	"strings"
	"time"
)

// RunAsyncInvoke submits a Shell command, or resumes polling the saved task.
func RunAsyncInvoke(viewOnly bool) error {
	state, err := LoadState()
	if err != nil {
		return err
	}
	toolID, err := ResolveToolID(state)
	if err != nil {
		return err
	}
	instanceID, err := RequireString(state, "instance_id")
	if err != nil {
		return err
	}
	timeout, err := positiveIntEnv("AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS", 600)
	if err != nil {
		return err
	}
	interval, err := positiveIntEnv("AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS", 2)
	if err != nil {
		return err
	}
	statePath, err := StatePath()
	if err != nil {
		return err
	}
	client, err := NewClient()
	if err != nil {
		return err
	}

	var taskID string
	if viewOnly {
		taskID, err = RequireString(state, "async_task_id")
		if err != nil {
			return err
		}
		printAsyncStage("[1/3] 读取已有任务（仅查询，不提交）")
	} else {
		command, configured := os.LookupEnv("AGENTKIT_ASYNC_COMMAND")
		if !configured {
			command = "sleep 20 && echo 'Hello from AgentKit sandbox!'"
		}
		if strings.TrimSpace(command) == "" {
			return fmt.Errorf("AGENTKIT_ASYNC_COMMAND must not be empty")
		}
		printAsyncStage("[1/3] 提交异步任务 (AsyncExecCommand)")
		printAsyncLine("- Command: " + command)
		request := map[string]any{
			"ToolId": toolID, "SessionId": instanceID, "Command": command,
		}
		if execDir := env("AGENTKIT_ASYNC_EXEC_DIR"); execDir != "" {
			request["ExecDir"] = execDir
		}
		response, err := client.AsyncExecCommand(request)
		if err != nil {
			return err
		}
		if err := validateAsyncTarget(response, toolID, instanceID, ""); err != nil {
			return err
		}
		taskID = response["TaskId"].(string)
		// Persist the task before polling so an interrupted wait can be resumed.
		delete(state, "async_view_response")
		delete(state, "async_viewed_at")
		state["async_task_id"] = taskID
		state["async_invoked_at"] = UTCNow()
		state["async_invoke_response"] = response
		if err := SaveState(state); err != nil {
			return err
		}
		printAsyncLine("- 提交状态: " + response["Status"].(string))
	}

	printAsyncLine("- ToolId: " + toolID)
	printAsyncLine("- SessionId: " + instanceID)
	printAsyncLine("- TaskId: " + taskID)
	printAsyncLine("- 状态文件: " + statePath)
	printAsyncStage("[2/3] 轮询执行结果 (ViewAsyncCommand)")
	printAsyncLine(fmt.Sprintf("- 查询间隔: %ds | 本地等待超时: %ds", interval, timeout))
	startedAt := time.Now()
	deadline := startedAt.Add(time.Duration(timeout) * time.Second)
	for pollCount := 1; ; pollCount++ {
		response, err := client.ViewAsyncCommand(map[string]any{
			"ToolId": toolID, "SessionId": instanceID, "TaskId": taskID,
		})
		if err != nil {
			return err
		}
		if err := validateAsyncTarget(response, toolID, instanceID, taskID); err != nil {
			return err
		}
		state["async_viewed_at"] = UTCNow()
		state["async_view_response"] = response
		if err := SaveState(state); err != nil {
			return err
		}
		status := strings.ToLower(strings.TrimSpace(response["Status"].(string)))
		now := time.Now()
		printAsyncLine(fmt.Sprintf("- 第 %d 次查询 | Status=%s | 已等待 %.1fs", pollCount, response["Status"], now.Sub(startedAt).Seconds()))
		if status != "running" {
			// JSON numbers decode to float64. An absent or null exit code is not zero.
			exitCode, hasExitCode := response["ExitCode"].(float64)
			// The API docs use Succeeded; live sandbox responses also use completed.
			if (status == "succeeded" || status == "completed") && hasExitCode && exitCode == 0 {
				printAsyncResult(response, "执行成功", statePath)
				return nil
			}
			printAsyncResult(response, "执行失败或状态异常", statePath)
			if status == "unknown" {
				return fmt.Errorf("task %s is Unknown; it may not exist or may have expired", taskID)
			}
			return fmt.Errorf("task %s did not succeed: Status=%q, ExitCode=%v; see async_view_response", taskID, response["Status"], response["ExitCode"])
		}
		// Running responses may contain a placeholder ExitCode; ignore it.
		remaining := deadline.Sub(now)
		if remaining <= 0 {
			printAsyncResult(response, "本地等待超时", statePath)
			printAsyncLine("- 远端命令未取消，可使用 --view-only 继续查询。")
			return fmt.Errorf("timed out after %ds waiting for task %s; the remote command is not cancelled. Use --view-only to query it again", timeout, taskID)
		}
		delay := time.Duration(interval) * time.Second
		if delay > remaining {
			delay = remaining
		}
		time.Sleep(delay)
	}
}

func validateAsyncTarget(response map[string]any, toolID, sessionID, taskID string) error {
	if response["ToolId"] != toolID || response["SessionId"] != sessionID {
		return fmt.Errorf("API returned an unexpected ToolId or SessionId")
	}
	returnedTaskID, ok := response["TaskId"].(string)
	if !ok || strings.TrimSpace(returnedTaskID) == "" {
		return fmt.Errorf("API returned an empty or invalid TaskId")
	}
	status, ok := response["Status"].(string)
	if !ok || strings.TrimSpace(status) == "" {
		return fmt.Errorf("API returned an empty or invalid Status")
	}
	if taskID != "" && returnedTaskID != taskID {
		return fmt.Errorf("ViewAsyncCommand returned an unexpected TaskId")
	}
	return nil
}

func printAsyncLine(message string) {
	fmt.Println(RedactSensitiveValues(message))
}

func printAsyncStage(title string) {
	printAsyncLine("\n**************** " + title + " ****************")
}

func printAsyncResult(response map[string]any, title, statePath string) {
	printAsyncStage("[3/3] " + title)
	exitCode := response["ExitCode"]
	if strings.EqualFold(strings.TrimSpace(response["Status"].(string)), "running") {
		exitCode = "尚未生效"
	}
	printAsyncLine(fmt.Sprintf("- Status=%s | ExitCode=%v", response["Status"], exitCode))
	printAsyncLine("---------------- 命令输出 (stdout + stderr) ----------------")
	output, _ := response["Output"].(string)
	if output == "" {
		output = "（无输出）"
	}
	printAsyncLine(output)
	printAsyncLine("---------------- 完整状态文件 ----------------")
	printAsyncLine(statePath)
}
