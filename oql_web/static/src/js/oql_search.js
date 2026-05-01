/** @odoo-module **/

import { SearchBar } from "@web/search/search_bar/search_bar";
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class OQLSearchBar extends SearchBar {
    setup() {
        super.setup();
        this.useOQL = useState({ value: false });
        this.oqlQuery = useState({ value: "" });
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.codeMirrorRef = useRef("codemirror");
        this.editor = null;
    }

    async onToggleOQL() {
        this.useOQL.value = !this.useOQL.value;
        
        if (this.useOQL.value) {
            // 切换到 OQL 模式时初始化编辑器
            await this.initCodeMirror();
        } else {
            // 切换回普通模式时销毁编辑器
            if (this.editor) {
                this.editor.toTextArea();
                this.editor = null;
            }
        }
    }

    async initCodeMirror() {
        if (this.editor || !this.codeMirrorRef.el) return;
        
        // 等待 DOM 更新
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const textarea = this.codeMirrorRef.el;
        if (!textarea) return;
        
        // 初始化 CodeMirror
        this.editor = CodeMirror.fromTextArea(textarea, {
            mode: "text/x-oql",
            lineNumbers: false,
            placeholder: "Enter OQL query...",
            extraKeys: {
                "Enter": (cm) => this.executeOQLSearch(),
                "Ctrl-Space": "autocomplete"
            }
        });
        
        // 设置初始值
        if (this.oqlQuery.value) {
            this.editor.setValue(this.oqlQuery.value);
        }
        
        // 监听变化
        this.editor.on("change", () => {
            this.oqlQuery.value = this.editor.getValue();
        });
        
        // 刷新编辑器
        this.editor.refresh();
    }

    async executeOQLSearch() {
        const query = this.oqlQuery.value.trim();
        if (!query) return;
        
        try {
            const model = this.env.searchModel.resModel;
            
            // 调用 searcho 方法
            const result = await this.orm.call(model, "searcho", [query], {
                context: this.env.searchModel.context
            });
            
            // 触发搜索更新
            this.env.searchModel.setDomain(result.domain || []);
            
            // 显示成功提示
            this.notification.add(`OQL Query executed: ${query}`, {
                type: "success"
            });
        } catch (error) {
            console.error("OQL Search Error:", error);
            this.notification.add(error.data?.message || "Invalid OQL query", {
                type: "danger"
            });
        }
    }

    onWillUnmount() {
        if (this.editor) {
            this.editor.toTextArea();
            this.editor = null;
        }
    }
}

// 注册组件
registry.category("search_components").add("oql_search_bar", OQLSearchBar);
