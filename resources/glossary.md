# 用語小辭典（Glossary）

> **繁體中文** | [简体中文](./glossary.zh-Hans.md) | [English](./glossary.en.md)

> 本路線圖會大量出現「LLM」、「RAG」、「MCP」、「agent」這類詞。讀到不懂的詞先在這裡查 30 秒，再回去讀 stage 內容。
>
> 每個詞**只給最小可用的解釋**（30-80 字 + 在哪一個 stage 講細的）——不是維基百科。

---

## 1. 基本概念

### LLM（Large Language Model，大語言模型）

GPT、Claude、Gemini 這類「給文字、回文字」的模型。本身是純函式：input prompt → output text。它**不會自己上網、不會記住上次對話**——這些都要外接系統來做。

📍 詳細：[Stage 1](../stages/01-llm-basics.md)

### Token

LLM 看到的不是「字」，是 **token**（次字單位）。中文 1 個字 ≈ 1.5-2 token，英文 1 個 word ≈ 1.3 token。LLM 計費跟 context window 都以 token 計。「100 萬 token context」≈ 75 萬中文字。

📍 詳細：[Stage 1](../stages/01-llm-basics.md)

### Context Window（上下文視窗）

LLM 一次能「看」多少 token。**2026 frontier**：Claude Sonnet 4.6 / Opus 4.7 1M、GPT-5.5 ~400k、Gemini 3.1 Pro 2M。**不是越大越好**——超過某個長度後 LLM 會「在中間遺漏」（Lost in the Middle）。

### Prompt（提示詞）

你給 LLM 的輸入文字。**Prompt engineering** 就是設計這段輸入讓 LLM 給好答案。System prompt（角色設定）+ user prompt（這次的問題）是基本結構。

📍 詳細：[Stage 2](../stages/02-prompt-engineering.md)

### Few-shot / Zero-shot

- **Zero-shot**：直接問問題不給範例。
- **Few-shot**：給 2-5 個 input → output 的範例後再問。**Few-shot 通常顯著提升準確度**，特別是格式要求嚴的任務。

### Chain-of-Thought（CoT，思維鏈）

要 LLM「先想再答」——加上「Let's think step by step」之類的指令，讓它輸出推理過程再給結論。**準確度通常會提升**，代價是 token 數變多。

---

## 2. Agent / 工具使用

### Agent（代理人）

讓 LLM **能呼叫外部 function、看結果、再決定下一步**的系統。本路線圖的核心主題。差別在於：純 LLM 是 Q&A、agent 是「LLM + tools + 迴圈」。

📍 詳細：[Stage 3](../stages/03-tool-use-and-hello-agent.md)

### Tool Use / Function Calling

讓 LLM 呼叫你定義好的 function（查 DB、算數學、開瀏覽器…）。LLM 回的不是文字而是 `{"function": "search", "args": {...}}`，你的程式去執行、把結果再丟回 LLM。

📍 詳細：[Stage 3](../stages/03-tool-use-and-hello-agent.md)
📍 schema 怎麼寫好：[Function Schema 設計 cheatsheet](schema-design-cheatsheet.md)

### ReAct（Reasoning + Acting）

最經典的 agent pattern：**Thought（想）→ Action（叫工具）→ Observation（看結果）→ Thought ...** 一直 loop 到答得出來。多數 agent framework 內部都實作這個。

📍 詳細：[Stage 3](../stages/03-tool-use-and-hello-agent.md)

### Structured Output（結構化輸出）

要 LLM 輸出 **JSON / 其他固定 schema**，而不是自由文字。各家 LLM API 都有 `response_format` 或類似旗標支援。Agent 框架幾乎都靠這個跟 LLM 溝通。

### Agent Loop

「LLM → tool → 結果 → LLM」這個重複的循環。Loop 結束條件可能是：LLM 說「I'm done」、跑超過 N 步、超出 budget。

### Reflection / 反思（Reflexion / Self-Refine）

agent 自我評估上一回合輸出、依評估結果調整下一回合的 pattern。對比於 error handling（外部 catch + retry），反思是 agent **內生的 self-critique**——通常實作成「Actor 出答案 → Critic 找問題 → Actor 看 critic feedback 再答」的 loop。production agent（Cursor / Cline / Claude Code）每天在跑變種反思。

**兩個版本**：
- **基本版 / Self-Refine**（single session、無持久記憶）→ 屬於 reasoning loop 機制、是 ReAct 的 sibling pattern
- **完整 Reflexion**（含 episodic memory、跨 trial 累積教訓）→ 需要持久記憶層

代表 paper：[Reflexion (Shinn 2023)](https://arxiv.org/abs/2303.11366)、[Self-Refine (Madaan 2023)](https://arxiv.org/abs/2303.17651)。

📍 基本版 concept + 路由：[Stage 3 §反思](../stages/03-tool-use-and-hello-agent.md#-反思reflexion--self-refine-概念--路由)
📍 帶持久記憶的完整版：[Stage 6 §進階：帶持久記憶的 Reflexion 完整版](../stages/06-memory-rag.md#-進階帶持久記憶的-reflexion-完整版--track-b-選讀)

---

## 3. Memory / Retrieval / RAG

### RAG（Retrieval-Augmented Generation）

「先撈相關資料，再丟給 LLM 一起答」的模式。流程：使用者問題 → 用 embedding 找出最相關的 K 段資料 → 把那 K 段塞進 prompt → LLM 答。**用來解決 LLM 不知道你私有資料 / 知識過期的問題**。

📍 詳細：[Stage 6](../stages/06-memory-rag.md)

### Vector DB / Embedding（向量資料庫 / 嵌入）

把文字（或圖片）轉成一串數字（向量），讓「意思接近」的東西在向量空間中距離近。Vector DB（Pinecone、Chroma、Qdrant 等）就是儲存 + 高效查詢這些向量的資料庫。RAG 的核心元件。

📍 詳細：[Stage 6](../stages/06-memory-rag.md)

### Semantic Search（語意搜尋）

用 embedding 比較「意思相似」而不是「字串完全相同」。「電動車怎麼充電」可以撈到「EV charging tutorial」。傳統關鍵字搜尋（BM25 等）做不到這個。

### Chunking（切塊）

把長文件切成適合 embedding 的小段（通常 200-1000 token）。**切法直接影響 RAG 品質**——切太碎丟脈絡、切太長相關度模糊。常見策略：固定大小、按段落、按結構（heading）。

### Hybrid Search（混合搜尋）

語意搜尋 + 關鍵字搜尋一起用，再 merge 排序。多半比單一方法準。production-grade RAG 標配。

### Reranking（重新排序）

第一輪 retrieval 撈 top-50，再用更貴但更準的模型（cross-encoder）重排成 top-5 給 LLM。Cohere Rerank、bge-reranker 等。

### Contextual Retrieval

Anthropic 2024 提的方法——chunk 加上「整份文件的脈絡摘要」一起 embed，避免「這 chunk 拿出來看不知道是哪份文件講的」問題。

📍 詳細：[Stage 6](../stages/06-memory-rag.md)

---

## 4. Multi-Agent

### Multi-Agent（多 agent）

多個 agent 互相協作完成一個任務。常見 pattern：

- **Supervisor + Worker**：一個 agent 規劃 / 分派、其他執行
- **Swarm（群集）**：平等的 agent 群，沒有固定 supervisor
- **Debate（辯論）**：多個 agent 各持立場、最後 consensus

📍 詳細：[Stage 7](../stages/07-multi-agent-production.md)

### Handoff

一個 agent 把任務交給另一個 agent。比直接 function call 多了「context 怎麼傳」、「失敗誰處理」的問題。

### A2A（Agent-to-Agent）Protocol

Google 推的 agent 之間溝通協定，類似 MCP 但用於 agent ↔ agent，不是 agent ↔ tool。

---

## 5. Claude Code 生態

### MCP（Model Context Protocol）

Anthropic 推的開放協定，讓任何 LLM host（Claude Code、Cursor、自寫 agent）都能用同一套介面去呼叫外部 tool server。把它想成「**LLM 的 USB 接口**」。

📍 詳細：[Stage 5.2](../stages/05-claude-code-ecosystem.md#52--mcpmodel-context-protocol-基礎)

### Skills / SKILL.md

Claude Code 的「行為包」。一個 Skill 就是一個資料夾含 `SKILL.md`（描述「在什麼情境要做什麼、可呼叫哪些 tool」），Claude Code 會根據當下情境自動載入合適的 skill。

📍 詳細：[Stage 5.3](../stages/05-claude-code-ecosystem.md#53--skillsclaude-code-的行為層)

### Plugin / Marketplace

把多個 Skills + slash commands + hooks + MCP 設定打包成一個發布單位。**Marketplace** 就是 plugin 的目錄，社群可以 `claude plugin install` 安裝別人寫好的。

📍 詳細：[Stage 5.4](../stages/05-claude-code-ecosystem.md#54--plugins-與-marketplaces)

### Slash Command

Claude Code 內以 `/` 開頭的指令（`/help`、`/compact`、`/plan` 等）。可以自訂——把一段 prompt 存到 `.claude/commands/<name>.md` 就變成 `/name`。

### CLAUDE.md

放在 project root 的 markdown 檔，Claude Code 每次啟動都會讀。寫 project 級的規則 / 規範 / context（用什麼語言、coding style、別動哪些檔等）。

### Hooks

在 Claude Code 動作前後執行的 script（pre-tool-use、post-tool-use、user-message-received 等）。可拿來做 git 自動 commit、log 記錄、行為攔截等。

### Subagent（子 agent）

主 Claude Code session 之外，spawn 出來跑特定任務的 agent。有自己的 context window。例如「給我一個 code-reviewer subagent 看看 diff」。

寫法：在 `.claude/agents/<name>.md` 放 frontmatter + system prompt + tool whitelist。主 session 用 Task tool invoke（自動 parallel / sequential）。**跟 framework-based multi-agent 對照**：subagent 不需要裝 LangGraph / CrewAI 等 framework、直接寫 markdown 即可；但綁 Claude Code runtime。完整教學見 [Stage 5.5](../stages/05-claude-code-ecosystem.md#55--subagentsclaude-code-原生-multi-agent-機制)。

---

## 6. Production / Eval / Cost

### Eval（評估框架）

針對 agent 跑一組 test case，量化它的準確度 / latency / cost。**production agent 沒有 eval 等於沒有測試**。常見工具：promptfoo、LangSmith、langfuse evals。

📍 詳細：[Stage 7](../stages/07-multi-agent-production.md)

### Observability

把 agent 內部跑的每一步（哪個 LLM call、哪個 tool、什麼結果）都記下來。出 bug 時能 replay。常見：langfuse、Helicone、weave。

📍 詳細：[Stage 7](../stages/07-multi-agent-production.md)

### Prompt Caching

LLM 把 prompt 前綴 cache 起來，下次同前綴只算 cache hit 的便宜價（Anthropic 90% off、OpenAI 50% off）。Long context + 重複 query 的場景可以省很多錢。

### Streaming（串流輸出）

LLM 邊生邊回（一個 token 一個 token），不是等全部生完才丟整段回來。讀者體驗較好（像在打字）；技術上用 SSE 或 chunked transfer。**production 互動式應用幾乎都開**。代價：客戶端要能 handle partial response、ReAct 內 tool call 解析要等到 stream 結束。

### Batch API（批次 API）

把大量 LLM 請求打包送（不要求即時），24 小時內回。**Anthropic / OpenAI 通常打 5 折**。適合非互動場景：批次摘要、批次分類、eval 跑大量 test case、ETL pipeline。**互動式 chat 不能用**——延遲對使用者體驗來說太久。

### Token Cost / Inference Cost

每次 LLM 呼叫的成本 = input tokens × input price + output tokens × output price。Agent 跑 ReAct loop 的成本可以累積很快——大 codebase grep 一次可能花 10 萬 token。

### Guardrails

防 LLM 做壞事的規則層——擋掉 prompt injection、PII 外流、有害輸出等。NeMo Guardrails、Guardrails AI 等。

---

## 7. 用詞 / Buzzword

### CLI Agent

跑在終端機的 agent（Claude Code、Codex、Aider、Gemini CLI 等）。對比於跑在 IDE 內（Cursor、Continue）或 web 上（ChatGPT、Claude.ai）。

📍 詳細：[Track A A1](../tracks/cli/A1-cli-intro.md)、[`resources/cli-agents-guide.md`](cli-agents-guide.md)

### BYO API Key（Bring Your Own）

工具支援你自己提供 API key 而不是綁訂閱。Aider / OpenCode / goose 等 CLI 都是 BYO；Claude Code / Codex 預設是訂閱制。

### Local LLM / On-Device

模型跑在你自己機器上（Ollama、llama.cpp、MLX、LocalAI 等），資料不外傳。隱私 OK 但能力比 frontier 模型有差。

📍 詳細：[Stage 1](../stages/01-llm-basics.md)

### Quantization（量化）

把模型權重從 fp16 壓到 int8 / int4，省記憶體跟速度，代價是準確度小幅降低。Local LLM 用戶常碰到（Q4_K_M、Q8_0 等）。

### Hallucination（幻覺）

LLM 「自信地說錯」——把不存在的 API 編出來、把錯的數字當成事實寫。所有 production agent 都要防這個（用 RAG / structured output / eval / guardrails）。

### Frontier Model

當下最頂的模型（**2026-05**：GPT-5.5、Claude Opus 4.7、Gemini 3.1 Pro、DeepSeek-R2 等）。一般智慧任務用 frontier；簡單分類 / 翻譯用便宜的小模型省錢。

### Context Engineering

當「prompt 設計一個句子」已經 cover 不了，要動態組「**system prompt + tool definitions + memory + retrieved chunks + 多輪歷史**」——整個系統的設計學科。**Prompt engineering 的下一層**。

📍 詳細：[Stage 2 結尾](../stages/02-prompt-engineering.md) / [Stage 6](../stages/06-memory-rag.md) / [Stage 7](../stages/07-multi-agent-production.md)
📍 延伸：[`Meirtz/Awesome-Context-Engineering`](https://github.com/Meirtz/Awesome-Context-Engineering)

### Harness Engineering

把 agent 包成 production system 的工具帶設計——agent loop / tool registry / context manager / permissions / safety layer / memory layer / eval / observability / retry / circuit breaker 等。Claude Code、Cursor、OpenCode 等 CLI agent 都是 harness。**framework 把 LLM 包成 agent，harness 把 agent 包成 product**。

對比：
- **Framework**（Stage 4）規範 **API**：你呼叫的介面長什麼樣
- **Harness**（本詞）規範 **runtime**：怎麼跑、怎麼 recovery、怎麼觀測

📍 **Discipline 級概念**（**8 元件** / prompt→context→harness lineage / framework vs harness）：[Stage 7 §Harness Engineering](../stages/07-multi-agent-production.md#-harness-engineering--production-agent-runtime-的工程學--本-stage-核心概念)
📍 **Reference implementation case study**（讀 Claude Code source）：[Stage 5 §5.6](../stages/05-claude-code-ecosystem.md#56--claude-code-source-解剖reference-harness-implementation-track-b-必看)
📍 延伸：[`anthropics/claude-agent-sdk-python`](https://github.com/anthropics/claude-agent-sdk-python)、[`ai-boost/awesome-harness-engineering`](https://github.com/ai-boost/awesome-harness-engineering)、[`ZhangHanDong/harness-engineering-from-cc-to-ai-coding`](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding)

---

## 7. Agent Interfaces

### Computer Use（螢幕級 agent）

Agent 透過 **screenshot → vision → 算座標 → 模擬鍵鼠** 操作真實桌面 app——不靠 API、直接像人類用螢幕。代表：Anthropic Claude Computer Use（Opus 4.7 / Sonnet 4.6）/ OpenAI Codex desktop / Google Gemini in Chrome。**2024-10 Anthropic 公開 beta 開啟、2026 OSWorld 達 76.26% superhuman**。

📍 完整解說 + 4 強對比：[Stage 8 §Computer Use](../stages/08-agent-interfaces.md#-computer-use--螢幕級-agent)

### Browser Use（web 級 agent）

Agent 操作網頁、主要用 **DOM-aware navigation**（直接 query CSS selector）+ 必要時 vision fallback。代表閉源：Atlas / Comet / Dia / Gemini in Chrome。代表 OSS：[browser-use](https://github.com/browser-use/browser-use)（★ 86k+）。

📍 完整解說 + 5 強對比 + OSS 框架：[Stage 8 §Browser Use](../stages/08-agent-interfaces.md#-browser-use--web-級-agent)

### Sandbox（程式碼隔離環境）

讓 agent 寫的 code 在隔離環境跑、不在 host 機器——避免 agent `rm -rf /` / 連 internet 泄資料 / 偷 credentials 等災難。代表：E2B（Firecracker microVM）/ Daytona（Container）/ Modal（GPU sandbox）/ Vercel / Cloudflare。**OpenAI Agents SDK 2026-04 內建支援這些 provider**。

📍 完整 9-row 術語小辭典（含 microVM / Container 差異）+ 7 強對比：[Stage 8 §Code Sandbox](../stages/08-agent-interfaces.md#-code-execution-sandbox--隔離環境含術語小辭典)

### microVM（micro Virtual Machine）

VM 的精簡版、極小 footprint、啟動 < 100ms 但仍**獨立 kernel**——介於 Docker container（快 + 弱隔離）跟 full VM（慢 + 強隔離）之間。**Agent sandbox 多半選 microVM**。代表實作：[Firecracker](#firecracker)（AWS、E2B 用）。

📍 完整對比：[Stage 8 §術語小辭典](../stages/08-agent-interfaces.md#-隔離技術術語小辭典)

### Firecracker

AWS 開源的 microVM、Rust 寫、**AWS Lambda 底層** + E2B sandbox 用它做 isolation。強隔離 + 快啟動兼顧。

📍 [Stage 8 §術語小辭典](../stages/08-agent-interfaces.md#-隔離技術術語小辭典)

### gVisor

Google 寫的「用戶空間 kernel」、攔截 syscall 自己模擬、**不用 hypervisor**——介於 container 跟 VM。

📍 [Stage 8 §術語小辭典](../stages/08-agent-interfaces.md#-隔離技術術語小辭典)

---

## 找不到的詞？

- 看 [Stage 5.2 — MCP](../stages/05-claude-code-ecosystem.md#52--mcpmodel-context-protocol-基礎) / [5.3 — Skills](../stages/05-claude-code-ecosystem.md#53--skillsclaude-code-的行為層) / [5.4 — Plugins](../stages/05-claude-code-ecosystem.md#54--plugins-與-marketplaces) 的內文
- 看 [Stage 1](../stages/01-llm-basics.md) / [Stage 6](../stages/06-memory-rag.md) / [Stage 7](../stages/07-multi-agent-production.md) / [Stage 8](../stages/08-agent-interfaces.md) 的延伸閱讀清單
- 找不到的詞 → 開 issue 或直接 PR 加進這份小辭典
