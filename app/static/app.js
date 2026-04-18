(function () {
    const body = document.body;
    const composer = document.getElementById("composer");
    const runButton = document.getElementById("run-button");
    const statusText = document.getElementById("status-text");
    const stageFeed = document.getElementById("stage-feed");
    const emptyState = document.getElementById("empty-state");
    const focusNotesInput = document.getElementById("focus-notes-input");
    const composerHint = document.getElementById("composer-hint");
    const resultDock = document.getElementById("result-dock");
    const resultBadge = document.getElementById("result-badge");
    const resultCopy = document.getElementById("result-copy");
    const downloadMd = document.getElementById("download-md");
    const modalHost = document.getElementById("modal-host");
    const uploadModal = document.getElementById("upload-modal");
    const resumeModal = document.getElementById("resume-modal");
    const jdModal = document.getElementById("jd-modal");
    const uploadInput = document.getElementById("modal-resume-file");
    const uploadHint = document.getElementById("upload-hint");
    const resumeTextarea = document.getElementById("modal-resume-text");
    const jdTextarea = document.getElementById("modal-jd-text");
    const openModalButtons = document.querySelectorAll("[data-open-modal]");
    const closeModalButtons = document.querySelectorAll("[data-close-modal]");
    const saveUploadButton = document.getElementById("save-upload");
    const saveResumeButton = document.getElementById("save-resume");
    const saveJdButton = document.getElementById("save-jd");

    const state = {
        resumeFile: null,
        resumeText: resumeTextarea.value.trim(),
        jobDescription: jdTextarea.value.trim(),
        sessionId: "",
        stageMap: new Map(),
    };

    const stageOrder = ["input_summary", "match_analysis", "completion"];
    const stageTitles = {
        input_summary: "任务输入",
        match_analysis: "匹配诊断与优化建议",
        completion: "完成状态",
    };

    function escapeHtml(value) {
        return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderInlineMarkdown(text) {
        let safe = escapeHtml(text);
        safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
        safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        return safe;
    }

    function renderMarkdown(markdown) {
        const lines = markdown.replace(/\r/g, "").split("\n");
        const html = [];
        let paragraph = [];
        let listItems = [];
        let codeLines = [];
        let inCodeBlock = false;

        function flushParagraph() {
            if (!paragraph.length) {
                return;
            }
            html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
            paragraph = [];
        }

        function flushList() {
            if (!listItems.length) {
                return;
            }
            html.push(`<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
            listItems = [];
        }

        function flushCode() {
            if (!codeLines.length) {
                return;
            }
            html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
            codeLines = [];
        }

        for (const line of lines) {
            if (line.startsWith("```")) {
                flushParagraph();
                flushList();
                if (inCodeBlock) {
                    flushCode();
                    inCodeBlock = false;
                } else {
                    inCodeBlock = true;
                }
                continue;
            }

            if (inCodeBlock) {
                codeLines.push(line);
                continue;
            }

            if (!line.trim()) {
                flushParagraph();
                flushList();
                continue;
            }

            if (/^###\s+/.test(line)) {
                flushParagraph();
                flushList();
                html.push(`<h3>${renderInlineMarkdown(line.replace(/^###\s+/, ""))}</h3>`);
                continue;
            }

            if (/^##\s+/.test(line)) {
                flushParagraph();
                flushList();
                html.push(`<h2>${renderInlineMarkdown(line.replace(/^##\s+/, ""))}</h2>`);
                continue;
            }

            if (/^#\s+/.test(line)) {
                flushParagraph();
                flushList();
                html.push(`<h1>${renderInlineMarkdown(line.replace(/^#\s+/, ""))}</h1>`);
                continue;
            }

            if (/^\s*[-*]\s+/.test(line)) {
                flushParagraph();
                listItems.push(line.replace(/^\s*[-*]\s+/, ""));
                continue;
            }

            paragraph.push(line.trim());
        }

        flushParagraph();
        flushList();
        flushCode();
        return html.join("");
    }

    function setStatus(label) {
        statusText.textContent = label;
    }

    function setBusy(isBusy) {
        runButton.disabled = isBusy;
        runButton.textContent = isBusy ? "处理中..." : "开始优化";
    }

    function updateInputStatus() {
        const parts = [];
        parts.push(state.resumeFile ? `文件：${state.resumeFile.name}` : "未上传文件");
        parts.push(state.resumeText ? "已填写简历文本" : "未填写简历文本");
        parts.push(state.jobDescription ? "已填写 JD 信息" : "未填写 JD 信息");
        composerHint.textContent = parts.join(" · ");
    }

    function resetDownloadState() {
        downloadMd.href = "#";
        downloadMd.classList.add("disabled");
        downloadMd.setAttribute("aria-disabled", "true");
        resultBadge.textContent = "待生成";
        resultBadge.classList.remove("is-ready");
        resultCopy.textContent = "生成完成后，这里会启用 Markdown 下载按钮。";
        resultDock.open = false;
    }

    function setDownloadState(url) {
        downloadMd.href = url;
        downloadMd.classList.remove("disabled");
        downloadMd.setAttribute("aria-disabled", "false");
        resultBadge.textContent = "已就绪";
        resultBadge.classList.add("is-ready");
        resultCopy.textContent = "优化后的简历已生成，点击下方按钮直接下载 Markdown 版本。";
    }

    function renderEmptyState() {
        stageFeed.innerHTML = "";
        stageFeed.appendChild(emptyState);
        emptyState.hidden = false;
    }

    function resetStages() {
        state.stageMap.clear();
        renderEmptyState();
    }

    function createStage(stageKey, title) {
        if (!emptyState.hidden) {
            emptyState.hidden = true;
            emptyState.remove();
        }

        const details = document.createElement("details");
        details.className = "stage-card is-streaming";
        details.open = true;
        details.dataset.stage = stageKey;

        const summary = document.createElement("summary");
        summary.className = "stage-summary";

        const copy = document.createElement("div");
        const eyebrow = document.createElement("p");
        eyebrow.className = "stage-eyebrow";
        eyebrow.textContent = stageTitles[stageKey] || title;
        const heading = document.createElement("h3");
        heading.textContent = title;
        copy.appendChild(eyebrow);
        copy.appendChild(heading);

        const status = document.createElement("span");
        status.className = "stage-status";
        status.textContent = "生成中";

        summary.appendChild(copy);
        summary.appendChild(status);

        const content = document.createElement("div");
        content.className = "stage-content markdown-body typing";

        details.appendChild(summary);
        details.appendChild(content);

        stageFeed.appendChild(details);
        stageFeed.scrollTop = stageFeed.scrollHeight;

        const record = {
            details,
            content,
            status,
            rawMarkdown: "",
        };
        state.stageMap.set(stageKey, record);
        return record;
    }

    function ensureStage(stageKey, title) {
        if (state.stageMap.has(stageKey)) {
            return state.stageMap.get(stageKey);
        }
        return createStage(stageKey, title);
    }

    function appendStageMarkdown(stageKey, title, delta) {
        const stage = ensureStage(stageKey, title);
        stage.rawMarkdown += delta || "";
        stage.content.innerHTML = renderMarkdown(stage.rawMarkdown);
        stageFeed.scrollTop = stageFeed.scrollHeight;
    }

    function completeStage(stageKey) {
        const stage = state.stageMap.get(stageKey);
        if (!stage) {
            return;
        }
        stage.details.classList.remove("is-streaming");
        stage.details.classList.add("is-complete");
        stage.status.textContent = "已完成";
        stage.content.classList.remove("typing");
    }

    function appendAlert(message) {
        if (!emptyState.hidden) {
            emptyState.hidden = true;
            emptyState.remove();
        }
        const alert = document.createElement("section");
        alert.className = "server-error";
        alert.textContent = message;
        stageFeed.appendChild(alert);
        stageFeed.scrollTop = stageFeed.scrollHeight;
    }

    function openModal(modalId) {
        const modalMap = [uploadModal, resumeModal, jdModal];
        modalMap.forEach((modal) => {
            modal.hidden = modal.id !== modalId;
        });
        if (modalId === "resume-modal") {
            resumeTextarea.value = state.resumeText;
            resumeTextarea.focus();
        } else if (modalId === "jd-modal") {
            jdTextarea.value = state.jobDescription;
            jdTextarea.focus();
        } else if (modalId === "upload-modal") {
            uploadHint.textContent = state.resumeFile ? `当前文件：${state.resumeFile.name}` : "未选择文件";
            uploadInput.focus();
        }
        modalHost.hidden = false;
    }

    function closeModals() {
        modalHost.hidden = true;
        uploadModal.hidden = true;
        resumeModal.hidden = true;
        jdModal.hidden = true;
    }

    function parseSSEBlock(block) {
        let eventName = "message";
        const dataLines = [];
        for (const line of block.split("\n")) {
            if (line.startsWith("event:")) {
                eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
                dataLines.push(line.slice(5).trimStart());
            }
        }
        if (!dataLines.length) {
            return null;
        }
        return {
            eventName,
            payload: JSON.parse(dataLines.join("\n")),
        };
    }

    async function streamOptimize(formData) {
        const response = await fetch("/api/optimize-stream", {
            method: "POST",
            body: formData,
        });

        if (!response.ok || !response.body) {
            throw new Error("流式请求启动失败，请刷新页面后重试。");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            let splitIndex = buffer.indexOf("\n\n");
            while (splitIndex !== -1) {
                const block = buffer.slice(0, splitIndex);
                buffer = buffer.slice(splitIndex + 2);
                const parsed = parseSSEBlock(block);
                if (parsed) {
                    handleEvent(parsed.eventName, parsed.payload);
                }
                splitIndex = buffer.indexOf("\n\n");
            }
        }
    }

    function handleEvent(eventName, payload) {
        switch (eventName) {
            case "session":
                state.sessionId = payload.session_id || "";
                break;
            case "status":
                setStatus(payload.label || "处理中");
                break;
            case "stage_start":
                ensureStage(payload.stage, payload.title || stageTitles[payload.stage] || "执行阶段");
                break;
            case "stage_delta":
                appendStageMarkdown(payload.stage, stageTitles[payload.stage] || "执行阶段", payload.delta_markdown || "");
                break;
            case "stage_done":
                completeStage(payload.stage);
                break;
            case "export_ready":
                setDownloadState(payload.download_url);
                break;
            case "error":
                setStatus("执行失败");
                appendAlert(payload.message || "发生未知错误。");
                break;
            default:
                break;
        }
    }

    openModalButtons.forEach((button) => {
        button.addEventListener("click", function () {
            openModal(button.dataset.openModal);
        });
    });

    closeModalButtons.forEach((button) => {
        button.addEventListener("click", closeModals);
    });

    modalHost.addEventListener("click", function (event) {
        if (event.target.matches("[data-close-modal]")) {
            closeModals();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !modalHost.hidden) {
            closeModals();
        }
    });

    uploadInput.addEventListener("change", function () {
        const file = uploadInput.files && uploadInput.files[0];
        uploadHint.textContent = file ? `待保存文件：${file.name}` : "未选择文件";
    });

    saveUploadButton.addEventListener("click", function () {
        const file = uploadInput.files && uploadInput.files[0];
        if (file) {
            state.resumeFile = file;
        }
        updateInputStatus();
        closeModals();
    });

    saveResumeButton.addEventListener("click", function () {
        state.resumeText = resumeTextarea.value.trim();
        updateInputStatus();
        closeModals();
    });

    saveJdButton.addEventListener("click", function () {
        state.jobDescription = jdTextarea.value.trim();
        updateInputStatus();
        closeModals();
    });

    composer.addEventListener("submit", async function (event) {
        event.preventDefault();
        resetStages();
        resetDownloadState();
        setBusy(true);
        setStatus("任务已提交");

        if (!state.resumeText && !state.resumeFile) {
            appendAlert("请先上传简历文件或粘贴简历文本。");
            setStatus("缺少简历输入");
            setBusy(false);
            return;
        }

        if (!state.jobDescription) {
            appendAlert("请先填写 JD 信息。");
            setStatus("缺少 JD 信息");
            setBusy(false);
            return;
        }

        if (body.dataset.llmReady !== "true") {
            appendAlert("当前没有检测到 DEEPSEEK_API_KEY，无法继续生成。");
            setStatus("缺少模型配置");
            setBusy(false);
            return;
        }

        const formData = new FormData();
        formData.append("resume_text", state.resumeText);
        formData.append("job_description", state.jobDescription);
        formData.append("focus_notes", focusNotesInput.value.trim());
        if (state.resumeFile) {
            formData.append("resume_file", state.resumeFile);
        }

        try {
            await streamOptimize(formData);
        } catch (error) {
            appendAlert(error.message || "流式连接失败。");
            setStatus("连接失败");
        } finally {
            setBusy(false);
        }
    });

    resetStages();
    resetDownloadState();
    updateInputStatus();
})();
