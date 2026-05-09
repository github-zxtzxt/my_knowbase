import sys
import re
import os
import time
from playwright.sync_api import sync_playwright

# Windows 控制台默认 GBK，改成 UTF-8 避免中文乱码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def make_filename(url: str, first_msg: str) -> str:
    """用首条用户消息 + URL ID 生成有辨识度的文件名"""
    # 提取 URL 中的分享 ID
    url_id = re.sub(r'^https?://|/$', '', url).rstrip('/').split('/')[-1] or "chat"
    url_id = re.sub(r'[\\/*?:"<>|]', '', url_id)[:20]

    # 用首条消息做标题
    title = first_msg.strip().split('\n')[0] if first_msg else ""
    title = re.sub(r'[\\/*?:"<>|]', '', title)
    title = re.sub(r'\s+', '-', title)
    title = title[:40].strip('-') or "deepseek-chat"

    return f"{title}-{url_id}.md"


def extract_deepseek_chat(url: str, output_dir: str = "raw/articles"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=120000)

        try:
            page.wait_for_selector(".ds-message", timeout=15000)
        except Exception:
            print("[!] No .ds-message found, falling back to body text.")
            full_text = page.inner_text("body")
            browser.close()
            _save_markdown_raw(full_text, output_dir, url, "")
            return

        # 解除虚拟列表的高度限制，强制 React 渲染全部消息到 DOM
        page.evaluate("""() => {
            const vl = document.querySelector('.ds-virtual-list');
            if (!vl) return;
            vl.style.setProperty('height', 'auto', 'important');
            vl.style.setProperty('max-height', 'none', 'important');
            vl.style.setProperty('overflow', 'visible', 'important');
            vl.style.setProperty('contain', 'none', 'important');
            // 也解除祖先容器的裁剪
            let p = vl.parentElement;
            while (p) {
                const s = getComputedStyle(p);
                if (s.overflow !== 'visible') {
                    p.style.setProperty('overflow', 'visible', 'important');
                }
                if (s.maxHeight !== 'none') {
                    p.style.setProperty('max-height', 'none', 'important');
                }
                p.style.setProperty('contain', 'none', 'important');
                p = p.parentElement;
            }
        }""")
        time.sleep(3)  # 等 React 重新渲染全部消息

        # JS: HTML → Markdown 转换 + 消息提取
        messages_data = page.evaluate("""() => {

            // ── 内联元素处理（返回纯文本/行内 markdown） ──
            function inlineToMd(el) {
                let out = '';
                for (const child of el.childNodes) {
                    if (child.nodeType === 3) { // Text node
                        out += child.textContent;
                    } else if (child.nodeType === 1) {
                        const tag = child.tagName.toLowerCase();
                        if (tag === 'strong' || tag === 'b') {
                            out += '**' + inlineToMd(child) + '**';
                        } else if (tag === 'em' || tag === 'i') {
                            out += '*' + inlineToMd(child) + '*';
                        } else if (tag === 'code') {
                            out += '`' + child.textContent + '`';
                        } else if (tag === 'a') {
                            const href = child.getAttribute('href') || '';
                            out += '[' + inlineToMd(child) + '](' + href + ')';
                        } else if (tag === 'span') {
                            out += inlineToMd(child);
                        } else if (tag === 'img') {
                            const alt = child.getAttribute('alt') || '';
                            const src = child.getAttribute('src') || '';
                            out += '![' + alt + '](' + src + ')';
                        } else if (tag === 'br') {
                            out += '\\n';
                        } else {
                            out += inlineToMd(child);
                        }
                    }
                }
                return out;
            }

            // ── 列表处理（支持嵌套） ──
            function processList(listEl, indent, ordered) {
                let out = '';
                let idx = 1;
                for (const li of listEl.children) {
                    if (li.tagName.toLowerCase() !== 'li') continue;
                    const marker = ordered ? (idx + '.') : '-';
                    out += processListItem(li, indent, marker);
                    idx++;
                }
                return out;
            }

            function processListItem(li, indent, marker) {
                const prefix = ' '.repeat(indent);
                let textParts = [];
                let suffix = '';

                for (const child of li.childNodes) {
                    if (child.nodeType === 3) {
                        const t = child.textContent.trim();
                        if (t) textParts.push(t);
                    } else if (child.nodeType === 1) {
                        const ctag = child.tagName.toLowerCase();
                        if (ctag === 'ul') {
                            suffix += processList(child, indent + 4, false);
                        } else if (ctag === 'ol') {
                            suffix += processList(child, indent + 4, true);
                        } else {
                            textParts.push(inlineToMd(child));
                        }
                    }
                }

                const text = textParts.join(' ').trim();
                let result = prefix + marker + ' ' + text + '\\n';
                if (suffix) result += suffix;
                return result;
            }

            // ── 块级元素处理 ──
            function blockToMd(el) {
                const tag = el.tagName.toLowerCase();

                // 代码块（裸 <pre>，可能是 <pre><code> 或直接 <pre> 内含文本）
                if (tag === 'pre') {
                    const code = el.querySelector('code');
                    const text = code ? code.textContent : el.textContent;
                    return '```\\n' + text.trimEnd() + '\\n```\\n\\n';
                }

                // DeepSeek 代码块包装 div (.md-code-block)
                // 结构: div.md-code-block > (banner-wrap, pre, svg icons)
                if (el.classList.contains('md-code-block')) {
                    const lang = el.getAttribute('data-lang') || '';
                    // DeepSeek 的 <pre> 里直接用 <span> 做语法高亮，没有 <code>
                    const pre = el.querySelector('pre');
                    const text = pre ? pre.textContent : el.textContent;
                    return '```' + lang + '\\n' + text.trimEnd() + '\\n```\\n\\n';
                }

                // 标题
                if (/^h[1-6]$/.test(tag)) {
                    const level = parseInt(tag[1]);
                    return '#'.repeat(level) + ' ' + inlineToMd(el) + '\\n\\n';
                }

                // 段落
                if (tag === 'p') {
                    return inlineToMd(el) + '\\n\\n';
                }

                // 无序列表 / 有序列表（支持嵌套）
                if (tag === 'ul' || tag === 'ol') {
                    return processList(el, 0, tag === 'ol') + '\\n';
                }

                // 引用块
                if (tag === 'blockquote') {
                    const lines = el.innerText.trim().split('\\n');
                    return lines.map(l => '> ' + l).join('\\n') + '\\n\\n';
                }

                // 水平线
                if (tag === 'hr') {
                    return '---\\n\\n';
                }

                // 表格
                if (tag === 'table') {
                    const rows = [];
                    el.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('th, td').forEach(cell => {
                            cells.push(inlineToMd(cell).replace(/\\|/g, '\\\\|').trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length === 0) return '';
                    const colCount = Math.max(...rows.map(r => r.length));
                    let out = '';
                    for (let i = 0; i < rows.length; i++) {
                        while (rows[i].length < colCount) rows[i].push('');
                        out += '| ' + rows[i].join(' | ') + ' |\\n';
                        if (i === 0) {
                            out += '| ' + rows[i].map(() => '---').join(' | ') + ' |\\n';
                        }
                    }
                    return out + '\\n';
                }

                // 默认：递归处理子元素
                let out = '';
                for (const child of el.childNodes) {
                    if (child.nodeType === 1) {
                        out += blockToMd(child);
                    } else if (child.nodeType === 3) {
                        const t = child.textContent.trim();
                        if (t) out += t + '\\n\\n';
                    }
                }
                return out;
            }

            // ── 清理并转换 ──
            function elementToMd(el) {
                const clone = el.cloneNode(true);

                // 先保存代码块语言标签，再删 banner
                clone.querySelectorAll('.md-code-block').forEach(cb => {
                    const langSpan = cb.querySelector('.md-code-block-banner-wrap span');
                    if (langSpan) {
                        cb.setAttribute('data-lang', langSpan.textContent.trim());
                    }
                });

                // 去掉 UI 按钮和图标
                clone.querySelectorAll(
                    'button, .md-code-block-banner-wrap, [role="button"], svg'
                ).forEach(e => e.remove());

                let out = '';
                for (const child of clone.childNodes) {
                    if (child.nodeType === 1) {
                        out += blockToMd(child);
                    } else if (child.nodeType === 3) {
                        const t = child.textContent.trim();
                        if (t) out += t + '\\n\\n';
                    }
                }
                return out.trim();
            }

            // ── 提取消息 ──
            const messages = [];
            const msgElements = document.querySelectorAll('.ds-message');
            msgElements.forEach(el => {
                const answerMd = el.querySelector(':scope > .ds-markdown');
                if (answerMd) {
                    // 助手消息
                    const answerText = elementToMd(answerMd);

                    const thinkEl = el.querySelector('[class*="think"]');
                    let thinkText = '';
                    if (thinkEl) {
                        // 思考过程里也可能有 markdown，同样转换
                        const thinkMd = thinkEl.querySelector('.ds-markdown');
                        thinkText = thinkMd ? elementToMd(thinkMd) : elementToMd(thinkEl);
                    }

                    messages.push({
                        role: 'assistant',
                        answer: answerText,
                        thinking: thinkText
                    });
                } else {
                    // 用户消息：纯文本即可
                    messages.push({
                        role: 'user',
                        content: el.innerText.trim()
                    });
                }
            });
            return messages;
        }""")

        browser.close()

        # 生成 Markdown
        md_lines = []
        for msg in messages_data:
            if msg['role'] == 'user':
                md_lines.append(f"**用户**：\n\n{msg['content']}\n\n")
            else:
                if msg.get('thinking'):
                    md_lines.append(
                        f"**助手**（思考过程）：\n\n{msg['thinking']}\n\n"
                    )
                md_lines.append(f"**助手**：\n\n{msg['answer']}\n\n")
            md_lines.append("---\n\n")

        markdown = "".join(md_lines)

        # 取第一条用户消息作为文件名标题
        first_user_msg = ""
        for m in messages_data:
            if m['role'] == 'user':
                first_user_msg = m.get('content', '')
                break

        _save_markdown_raw(markdown, output_dir, url, first_user_msg)


def _save_markdown_raw(markdown, output_dir, url, first_msg):
    os.makedirs(output_dir, exist_ok=True)
    filename = make_filename(url, first_msg)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"[+] Saved to: {filepath}")
    print(f"[+] Total chars: {len(markdown)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_deepseek.py <URL>")
        sys.exit(1)
    url = sys.argv[1]
    extract_deepseek_chat(url)
