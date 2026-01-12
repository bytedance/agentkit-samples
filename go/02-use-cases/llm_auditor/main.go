// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"fmt"
	"llm_auditor/auditor"
	"time"

	"github.com/volcengine/veadk-go/apps"
	"github.com/volcengine/veadk-go/apps/agentkit_server_app"
	"google.golang.org/adk/agent"
	"google.golang.org/adk/artifact"
	"google.golang.org/adk/session"
)

func main() {

	ctx := context.Background()
	llmAuditorAgent := auditor.GetLLmAuditorAgent(ctx)

	app := agentkit_server_app.NewAgentkitA2AServerApp(apps.ApiConfig{
		Port:         8000,
		WriteTimeout: 300 * time.Second,
		ReadTimeout:  300 * time.Second,
		IdleTimeout:  600 * time.Second,
	})

	err := app.Run(ctx, &apps.RunConfig{
		AgentLoader:     agent.NewSingleLoader(llmAuditorAgent),
		SessionService:  session.InMemoryService(),
		ArtifactService: artifact.InMemoryService(),
	})
	if err != nil {
		fmt.Printf("Run failed: %v", err)
	}
}
