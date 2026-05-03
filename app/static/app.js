(function () {
    const body = document.body;
    const composer = document.getElementById("composer");
    const runButton = document.getElementById("run-button");
    const statusText = document.getElementById("status-text");
    const stageFeed = document.getElementById("stage-feed");
    const focusNotesInput = document.getElementById("focus-notes-input");
    const composerHint = document.getElementById("composer-hint");
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
    const btnUploadLabel = document.getElementById("btn-upload-label");
    const btnResumeLabel = document.getElementById("btn-resume-label");
    const btnJdLabel = document.getElementById("btn-jd-label");

    const state = {
        resumeFile: null,
        resumeText: resumeTextarea.value.trim(),
        jobDescription: jdTextarea.value.trim(),
        sessionId: "",
        stageMap: new Map(),
        phase: "idle",
    };

    const stageTitles = {
        match_score: "匹配度评分",
        detail_analysis: "详细匹配分析",
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
        let tableRows = [];
        let inCodeBlock = false;

        function flushParagraph() {
            if (!paragraph.length) return;
            html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
            paragraph = [];
        }
        function flushList() {
            if (!listItems.length) return;
            html.push(`<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
            listItems = [];
        }
        function flushCode() {
            if (!codeLines.length) return;
            html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
            codeLines = [];
        }
        function flushTable() {
            if (!tableRows.length) return;
            const rows = tableRows.map((r) =>
                r.split("|").map((c) => c.trim()).filter((c) => c !== "")
            ).filter((r) => r.length > 0 && !r.every((c) => /^[-:]+$/.test(c)));
            if (!rows.length) { tableRows = []; return; }
            let tbl = '<table class="md-table">';
            rows.forEach((cells, i) => {
                tbl += i === 0 ? "<thead><tr>" : "<tr>";
                cells.forEach((c) => {
                    tbl += i === 0 ? `<th>${renderInlineMarkdown(c)}</th>` : `<td>${renderInlineMarkdown(c)}</td>`;
                });
                tbl += i === 0 ? "</tr></thead><tbody>" : "</tr>";
            });
            tbl += "</tbody></table>";
            html.push(tbl);
            tableRows = [];
        }

        for (const line of lines) {
            if (line.startsWith("```")) {
                flushParagraph(); flushList(); flushTable();
                inCodeBlock ? (flushCode(), inCodeBlock = false) : (inCodeBlock = true);
                continue;
            }
            if (inCodeBlock) { codeLines.push(line); continue; }
            if (!line.trim()) { flushParagraph(); flushList(); flushTable(); continue; }
            if (/^###\s+/.test(line)) { flushParagraph(); flushList(); flushTable(); html.push(`<h3>${renderInlineMarkdown(line.replace(/^###\s+/, ""))}</h3>`); continue; }
            if (/^##\s+/.test(line)) { flushParagraph(); flushList(); flushTable(); html.push(`<h2>${renderInlineMarkdown(line.replace(/^##\s+/, ""))}</h2>`); continue; }
            if (/^#\s+/.test(line)) { flushParagraph(); flushList(); flushTable(); html.push(`<h1>${renderInlineMarkdown(line.replace(/^#\s+/, ""))}</h1>`); continue; }
            if (/^\s*\|/.test(line) && line.includes("|")) { flushParagraph(); flushList(); tableRows.push(line); continue; }
            if (/^\s*[-*]\s+/.test(line)) { flushParagraph(); flushTable(); listItems.push(line.replace(/^\s*[-*]\s+/, "")); continue; }
            flushTable();
            paragraph.push(line.trim());
        }
        flushParagraph(); flushList(); flushCode(); flushTable();
        return html.join("");
    }

    function setStatus(label) {
        statusText.textContent = label;
    }

    // ---- Toolbar checkmarks ----
    function updateToolbarCheckmarks() {
        btnUploadLabel.className = "btn-label" + (state.resumeFile ? " has-data" : "");
        btnResumeLabel.className = "btn-label" + (state.resumeText && !state.resumeFile ? " has-data" : "");
        btnJdLabel.className = "btn-label" + (state.jobDescription ? " has-data" : "");
        btnUploadLabel.textContent = state.resumeFile ? "✓ 上传简历" : "上传简历";
        btnResumeLabel.textContent = state.resumeText && !state.resumeFile ? "✓ 粘贴简历" : "粘贴简历";
        btnJdLabel.textContent = state.jobDescription ? "✓ JD 信息" : "JD 信息";
    }

    // ---- Run button ----
    function updateRunButton() {
        switch (state.phase) {
            case "idle":
                runButton.textContent = "开始优化";
                runButton.disabled = false;
                runButton.className = "primary-button";
                break;
            case "running_score":
                runButton.textContent = "匹配度计算中...";
                runButton.disabled = true;
                runButton.className = "primary-button";
                break;
            case "score_done":
                runButton.textContent = "开始分析";
                runButton.disabled = false;
                runButton.className = "primary-button confirm-button";
                break;
            case "running_analysis":
                runButton.textContent = "分析中...";
                runButton.disabled = true;
                runButton.className = "primary-button";
                break;
            case "done":
                runButton.innerHTML = '<span class="check-icon">&#10003;</span> 已完成';
                runButton.disabled = false;
                runButton.className = "primary-button done-button";
                break;
        }
    }

    function updateInputStatus() {
        const parts = [];
        if (state.resumeFile) parts.push(`文件：${state.resumeFile.name}`);
        else if (state.resumeText) parts.push("已填写简历文本");
        else parts.push("未上传文件");
        parts.push(state.jobDescription ? "已填写 JD 信息" : "未填写 JD 信息");
        composerHint.textContent = parts.join(" · ");
    }

    function resetStages() {
        state.stageMap.clear();
        stageFeed.innerHTML = "";
    }

    // ---- Stage card with spinner in top-right ----
    function createStage(stageKey, title) {
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
        status.style.display = "none";

        summary.appendChild(copy);
        summary.appendChild(status);

        const content = document.createElement("div");
        content.className = "stage-content markdown-body typing";

        details.appendChild(summary);
        details.appendChild(content);

        stageFeed.appendChild(details);
        stageFeed.scrollTop = stageFeed.scrollHeight;

        const record = { details, content, status, rawMarkdown: "" };
        state.stageMap.set(stageKey, record);
        return record;
    }

    function ensureStage(stageKey, title) {
        if (state.stageMap.has(stageKey)) return state.stageMap.get(stageKey);
        return createStage(stageKey, title);
    }

    function completeStage(stageKey) {
        const stage = state.stageMap.get(stageKey);
        if (!stage) return;
        stage.details.classList.remove("is-streaming");
        stage.details.classList.add("is-complete");
        stage.status.textContent = "已完成";
        stage.status.style.display = "";
        stage.content.classList.remove("typing");
    }

    // ---- Render score JSON as structured card ----
    function renderScoreCard(payload) {
        const stage = state.stageMap.get("match_score");
        if (!stage) return;

        const score = payload.score || 0;
        const summary = escapeHtml(payload.summary || "");

        let color = "#c65a4b";
        let label = "待提升";
        if (score >= 70) { color = "#2166e5"; label = "良好匹配"; }
        if (score >= 85) { color = "#177f62"; label = "高度匹配"; }

        let html = '<div class="score-card">';
        html += '<div class="score-header">';
        html += `<span class="score-badge" style="--score-color:${color}">${score}%</span>`;
        html += `<span class="score-label" style="color:${color}">${label}</span>`;
        html += '</div>';
        html += '<div class="score-bar-track"><div class="score-bar-fill" style="--bar-color:' + color + ';width:' + score + '%"></div></div>';
        html += `<p class="score-summary">${summary}</p>`;
        html += '<button type="button" class="primary-button confirm-button score-optimize-btn" id="score-optimize-btn">开始分析</button>';
        html += '</div>';

        stage.content.innerHTML = html;
        stage.content.classList.remove("typing");
        stageFeed.scrollTop = stageFeed.scrollHeight;

        // Bind optimize button
        const btn = document.getElementById("score-optimize-btn");
        if (btn) {
            btn.addEventListener("click", function () {
                startDetailAnalysis();
            });
        }
    }

    // ---- Start detail analysis from score card button ----
    async function startDetailAnalysis() {
        const scoreBtn = document.getElementById("score-optimize-btn");
        if (scoreBtn) {
            scoreBtn.disabled = true;
            scoreBtn.textContent = "分析中...";
        }

        state.phase = "running_analysis";
        updateRunButton();
        setStatus("正在生成详细分析");

        // Create detail analysis card
        createStage("detail_analysis", "详细匹配分析");

        const formData = new FormData();
        formData.append("session_id", state.sessionId);

        try {
            await streamRequest("/api/detail-stream", formData);
            state.phase = "done";
            updateRunButton();
            setStatus("全部完成");
            // Update score card button to completed
            if (scoreBtn) {
                scoreBtn.className = "primary-button done-button score-optimize-btn";
                scoreBtn.innerHTML = '<span class="check-icon">&#10003;</span> 已完成';
                scoreBtn.disabled = false;
            }
        } catch (error) {
            appendAlert(error.message || "分析请求失败。");
            setStatus("连接失败");
            state.phase = "idle";
            updateRunButton();
            if (scoreBtn) {
                scoreBtn.disabled = false;
                scoreBtn.textContent = "开始分析";
            }
        }
    }

    function appendStageMarkdown(stageKey, title, delta) {
        const stage = state.stageMap.get(stageKey);
        if (!stage) return;
        stage.rawMarkdown += delta || "";
        stage.content.innerHTML = renderMarkdown(stage.rawMarkdown);
        stageFeed.scrollTop = stageFeed.scrollHeight;
    }

    function appendAlert(message) {
        const alert = document.createElement("section");
        alert.className = "server-error";
        alert.textContent = message;
        stageFeed.appendChild(alert);
        stageFeed.scrollTop = stageFeed.scrollHeight;
    }

    // ---- Modals ----
    function openModal(modalId) {
        [uploadModal, resumeModal, jdModal].forEach((m) => { m.hidden = m.id !== modalId; });
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

    // ---- SSE parsing ----
    function parseSSEBlock(block) {
        let eventName = "message";
        const dataLines = [];
        for (const line of block.split("\n")) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
        }
        if (!dataLines.length) return null;
        return { eventName, payload: JSON.parse(dataLines.join("\n")) };
    }

    async function streamRequest(url, formData) {
        const response = await fetch(url, { method: "POST", body: formData });
        if (!response.ok || !response.body) throw new Error("请求启动失败，请刷新页面后重试。");
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let idx = buffer.indexOf("\n\n");
            while (idx !== -1) {
                const block = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 2);
                const parsed = parseSSEBlock(block);
                if (parsed) handleEvent(parsed.eventName, parsed.payload);
                idx = buffer.indexOf("\n\n");
            }
        }
        // Flush remaining buffer
        if (buffer.trim()) {
            const parsed = parseSSEBlock(buffer);
            if (parsed) handleEvent(parsed.eventName, parsed.payload);
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
                if (payload.stage === "input_summary") return;
                ensureStage(payload.stage, payload.title || stageTitles[payload.stage] || "执行阶段");
                break;
            case "stage_delta":
                if (payload.stage === "input_summary") return;
                appendStageMarkdown(payload.stage, stageTitles[payload.stage] || "执行阶段", payload.delta_markdown || "");
                break;
            case "stage_done":
                if (payload.stage === "input_summary") return;
                completeStage(payload.stage);
                break;
            case "score_ready":
                renderScoreCard(payload);
                state.phase = "score_done";
                updateRunButton();
                break;
            case "export_ready":
                const completionStage = state.stageMap.get("completion");
                if (completionStage) {
                    const dlBtn = document.createElement("a");
                    dlBtn.href = payload.download_url;
                    dlBtn.className = "primary-button completion-download-btn";
                    dlBtn.textContent = "下载优化简历";
                    dlBtn.style.display = "inline-flex";
                    dlBtn.style.marginTop = "6px";
                    dlBtn.style.textDecoration = "none";
                    dlBtn.style.alignSelf = "flex-start";
                    completionStage.content.appendChild(dlBtn);
                }
                break;
            case "error":
                setStatus("执行失败");
                appendAlert(payload.message || "发生未知错误。");
                state.phase = "idle";
                updateRunButton();
                break;
        }
    }

    // ---- Event listeners ----
    openModalButtons.forEach((button) => {
        button.addEventListener("click", function () { openModal(button.dataset.openModal); });
    });
    closeModalButtons.forEach((button) => {
        button.addEventListener("click", closeModals);
    });
    modalHost.addEventListener("click", function (event) {
        if (event.target.matches("[data-close-modal]")) closeModals();
    });
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !modalHost.hidden) closeModals();
    });

    uploadInput.addEventListener("change", function () {
        const file = uploadInput.files && uploadInput.files[0];
        uploadHint.textContent = file ? `待保存文件：${file.name}` : "未选择文件";
    });

    saveUploadButton.addEventListener("click", function () {
        const file = uploadInput.files && uploadInput.files[0];
        if (file) state.resumeFile = file;
        updateInputStatus();
        updateToolbarCheckmarks();
        closeModals();
    });

    saveResumeButton.addEventListener("click", function () {
        state.resumeText = resumeTextarea.value.trim();
        updateInputStatus();
        updateToolbarCheckmarks();
        closeModals();
    });

    saveJdButton.addEventListener("click", function () {
        state.jobDescription = jdTextarea.value.trim();
        updateInputStatus();
        updateToolbarCheckmarks();
        closeModals();
    });

    // ---- Main submit handler ----
    composer.addEventListener("submit", async function (event) {
        event.preventDefault();

        if (state.phase === "done") {
            resetStages();
            state.phase = "idle";
            updateRunButton();
            return;
        }

        if (state.phase === "score_done") {
            startDetailAnalysis();
            return;
        }

        if (state.phase === "running_score" || state.phase === "running_analysis") return;

        // Validate inputs
        resetStages();
        state.phase = "running_score";
        updateRunButton();
        setStatus("任务已提交");

        if (!state.resumeText && !state.resumeFile) {
            appendAlert("请先上传简历文件或粘贴简历文本。");
            setStatus("缺少简历输入");
            state.phase = "idle";
            updateRunButton();
            return;
        }
        if (!state.jobDescription) {
            appendAlert("请先填写 JD 信息。");
            setStatus("缺少 JD 信息");
            state.phase = "idle";
            updateRunButton();
            return;
        }
        if (body.dataset.llmReady !== "true") {
            appendAlert("当前没有检测到 XIAOMI_API_KEY，无法继续生成。");
            setStatus("缺少模型配置");
            state.phase = "idle";
            updateRunButton();
            return;
        }

        const formData = new FormData();
        formData.append("resume_text", state.resumeText);
        formData.append("job_description", state.jobDescription);
        formData.append("focus_notes", focusNotesInput.value.trim());
        if (state.resumeFile) formData.append("resume_file", state.resumeFile);

        try {
            await streamRequest("/api/analyze-stream", formData);
            if (state.phase !== "score_done") {
                state.phase = "idle";
                updateRunButton();
            }
        } catch (error) {
            appendAlert(error.message || "请求失败。");
            setStatus("连接失败");
            state.phase = "idle";
            updateRunButton();
        }
    });

    resetStages();
    updateInputStatus();
    updateToolbarCheckmarks();
    updateRunButton();
})();
