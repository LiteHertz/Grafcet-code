import json
import os
import time
import copy
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

JSON_PATH = os.path.join(os.path.dirname(__file__), "Projet 1 - H26.json")
POLL_INTERVAL_MS = 1000

NODE_KEYS_ORDER = ["category", "key", "location", "step", "text", "size"]
LINK_KEYS_ORDER = ["from", "to", "text"]


def reorder_node(obj):
    out = {}
    for k in NODE_KEYS_ORDER:
        out[k] = obj.get(k, "")
    # keep any extra keys at the end in original order
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    return out


def reorder_link(obj):
    out = {}
    for k in LINK_KEYS_ORDER:
        out[k] = obj.get(k, "")
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    return out


class GrafcetEditor(tk.Tk):
    def __init__(self, json_path):
        super().__init__()
        self.title("Grafcet JSON Editor")
        self.geometry("1000x600")
        self.json_path = json_path
        self.last_mtime = None
        self.raw = {}
        self.modified = False
        self._build_ui()
        self.load_json()
        self.poll_file()

    def _build_ui(self):
        pan = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        pan.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(pan, width=320)
        right = ttk.Frame(pan)
        pan.add(left, weight=1)
        pan.add(right, weight=3)

        # Top: file selector
        top_frame = ttk.Frame(right)
        top_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(top_frame, text="File:", font=(None, 10)).pack(side=tk.LEFT)
        self.file_label = ttk.Label(top_frame, text=os.path.basename(self.json_path), foreground="blue")
        self.file_label.pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT)

        # Tabs for nodes/links
        tabs = ttk.Notebook(left)
        tabs.pack(fill=tk.BOTH, expand=True)

        self.node_tab = ttk.Frame(tabs)
        self.link_tab = ttk.Frame(tabs)
        tabs.add(self.node_tab, text="Nodes")
        tabs.add(self.link_tab, text="Links")

        # Node listbox
        self.node_list = tk.Listbox(self.node_tab, selectmode=tk.MULTIPLE)
        self.node_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.node_list.bind("<<ListboxSelect>>", self.on_node_select)
        nb = ttk.Frame(self.node_tab)
        nb.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Button(nb, text="Add", command=self.add_node).pack(fill=tk.X)
        ttk.Button(nb, text="Del", command=self.delete_node).pack(fill=tk.X)
        ttk.Button(nb, text="Move Up", command=lambda: self.move_item(self.node_list, -1)).pack(fill=tk.X)
        ttk.Button(nb, text="Move Down", command=lambda: self.move_item(self.node_list, 1)).pack(fill=tk.X)
        
        # Offset controls for selected nodes
        ttk.Separator(nb, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(nb, text="Offset (sel.)", font=(None, 9)).pack(anchor=tk.W, padx=4)
        offset_frame = ttk.Frame(nb)
        offset_frame.pack(fill=tk.X, padx=4)
        ttk.Label(offset_frame, text="X:").pack(side=tk.LEFT)
        self.offset_x = ttk.Entry(offset_frame, width=6)
        self.offset_x.pack(side=tk.LEFT, padx=2)
        self.offset_x.insert(0, "0")
        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT)
        self.offset_y = ttk.Entry(offset_frame, width=6)
        self.offset_y.pack(side=tk.LEFT, padx=2)
        self.offset_y.insert(0, "0")
        ttk.Button(nb, text="Apply Offset", command=self.apply_offset).pack(fill=tk.X, padx=4, pady=4)

        # Link listbox
        self.link_list = tk.Listbox(self.link_tab)
        self.link_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.link_list.bind("<<ListboxSelect>>", self.on_link_select)
        lb = ttk.Frame(self.link_tab)
        lb.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Button(lb, text="Add", command=self.add_link).pack(fill=tk.X)
        ttk.Button(lb, text="Del", command=self.delete_link).pack(fill=tk.X)
        ttk.Button(lb, text="Move Up", command=lambda: self.move_item(self.link_list, -1)).pack(fill=tk.X)
        ttk.Button(lb, text="Move Down", command=lambda: self.move_item(self.link_list, 1)).pack(fill=tk.X)

        # Right: detail editor
        form = ttk.Frame(right)
        form.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.fields = {}

        # Generic fields area
        self.form_title = ttk.Label(form, text="Select a node or link to edit", font=(None, 12))
        self.form_title.pack(anchor=tk.W)
        self.form_area = ttk.Frame(form)
        self.form_area.pack(fill=tk.BOTH, expand=True)

        # Raw JSON editor (below the form area)
        raw_frame = ttk.LabelFrame(form, text="Raw JSON")
        raw_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        
        # Text + scrollbar area
        text_area = ttk.Frame(raw_frame)
        text_area.pack(fill=tk.BOTH, expand=True)
        self.raw_text = tk.Text(text_area, height=12)
        self.raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        raw_scroll = ttk.Scrollbar(text_area, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.raw_text['yscrollcommand'] = raw_scroll.set
        
        # Buttons area below text
        raw_btns = ttk.Frame(raw_frame)
        raw_btns.pack(fill=tk.X, pady=4)
        ttk.Button(raw_btns, text="Copy JSON", command=self.copy_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(raw_btns, text="Apply JSON", command=self.apply_json_textbox).pack(side=tk.LEFT, padx=2)
        ttk.Button(raw_btns, text="Paste & Apply", command=self.paste_and_apply).pack(side=tk.LEFT, padx=2)
        ttk.Button(raw_btns, text="Refresh JSON view", command=self.update_json_textbox).pack(side=tk.LEFT, padx=2)

        # bottom buttons
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="Save to file", command=self.save_json).pack(side=tk.RIGHT, padx=4, pady=4)
        ttk.Button(bottom, text="Reload from file", command=self.manual_reload).pack(side=tk.RIGHT, padx=4, pady=4)
        self.status = ttk.Label(bottom, text="Idle")
        self.status.pack(side=tk.LEFT)

    def clear_form(self):
        for w in self.form_area.winfo_children():
            w.destroy()
        self.fields = {}

    def build_form(self, keys):
        self.clear_form()
        for k in keys:
            row = ttk.Frame(self.form_area)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=k, width=12).pack(side=tk.LEFT)
            # use a multiline Text widget for the 'text' field to support returns/\n
            if k == 'text':
                txt = tk.Text(row, height=5)
                txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                self.fields[k] = txt
            else:
                ent = ttk.Entry(row)
                ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.fields[k] = ent
        ttk.Button(self.form_area, text="Apply", command=self.apply_fields).pack(pady=6)

    def set_status(self, text):
        self.status.config(text=text)

    def load_json(self):
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.raw = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON: {e}")
            self.raw = {"class": "GraphLinksModel", "nodeDataArray": [], "linkDataArray": []}
        self.last_mtime = os.path.getmtime(self.json_path) if os.path.exists(self.json_path) else None
        self.populate_lists()
        self.update_json_textbox()
        self.set_status(f"Loaded {os.path.basename(self.json_path)}")
        self.modified = False

    def populate_lists(self):
        self.node_list.delete(0, tk.END)
        self.link_list.delete(0, tk.END)
        nodes = self.raw.get('nodeDataArray', [])
        links = self.raw.get('linkDataArray', [])
        for i, n in enumerate(nodes):
            category = n.get('category', "")
            label = n.get('text') or n.get('step') or n.get('category') or str(n.get('key', i))
            prefix = f"[{category}] " if category else ""
            self.node_list.insert(tk.END, f"{i}: {prefix}{label}")
        for i, l in enumerate(links):
            label = l.get('text') or f"{l.get('from')}→{l.get('to')}"
            cat = l.get('category', "")
            prefix = f"[{cat}] " if cat else ""
            self.link_list.insert(tk.END, f"{i}: {prefix}{label}")

    def on_node_select(self, evt):
        sel = self.node_list.curselection()
        if not sel:
            return
        # For multi-select, only edit the first selected
        idx = sel[0]
        node = self.raw.get('nodeDataArray', [])[idx]
        self.form_title.config(text=f"Edit node #{idx}")
        keys = NODE_KEYS_ORDER[:]  # show standard node keys
        extra = [k for k in node.keys() if k not in keys]
        keys += extra
        self.build_form(keys)
        for k, widget in self.fields.items():
            val = node.get(k, "")
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", val)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, val)
        self.current = ('node', idx)

    def on_link_select(self, evt):
        sel = self.link_list.curselection()
        if not sel:
            return
        idx = sel[0]
        link = self.raw.get('linkDataArray', [])[idx]
        self.form_title.config(text=f"Edit link #{idx}")
        keys = LINK_KEYS_ORDER[:]  # standard link keys
        extra = [k for k in link.keys() if k not in keys]
        keys += extra
        self.build_form(keys)
        for k, widget in self.fields.items():
            val = link.get(k, "")
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", val)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, val)
        self.current = ('link', idx)

    def apply_fields(self):
        if not hasattr(self, 'current'):
            return
        typ, idx = self.current
        if typ == 'node':
            arr = self.raw.setdefault('nodeDataArray', [])
            obj = arr[idx]
            for k, widget in self.fields.items():
                if isinstance(widget, tk.Text):
                    val = widget.get("1.0", "end-1c")
                else:
                    val = widget.get()
                # try to convert numeric keys back to numbers where appropriate
                if k == 'key':
                    try:
                        obj[k] = int(val)
                    except:
                        obj[k] = val
                else:
                    obj[k] = val
            arr[idx] = obj
        else:
            arr = self.raw.setdefault('linkDataArray', [])
            obj = arr[idx]
            for k, widget in self.fields.items():
                if isinstance(widget, tk.Text):
                    val = widget.get("1.0", "end-1c")
                else:
                    val = widget.get()
                if k in ('from', 'to'):
                    try:
                        obj[k] = int(val)
                    except:
                        obj[k] = val
                else:
                    obj[k] = val
            arr[idx] = obj
        self.modified = True
        self.populate_lists()
        self.update_json_textbox()
        self.set_status("Modified (unsaved)")

    def add_node(self):
        nodes = self.raw.setdefault('nodeDataArray', [])
        new = {k: "" for k in NODE_KEYS_ORDER}
        new['key'] = self._next_free_key()
        nodes.append(new)
        self.populate_lists()
        self.node_list.select_set(tk.END)
        self.on_node_select(None)
        self.modified = True

    def delete_node(self):
        sel = self.node_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if not messagebox.askyesno("Delete", f"Delete node #{idx}?"):
            return
        self.raw['nodeDataArray'].pop(idx)
        self.populate_lists()
        self.modified = True

    def add_link(self):
        links = self.raw.setdefault('linkDataArray', [])
        new = {k: "" for k in LINK_KEYS_ORDER}
        links.append(new)
        self.populate_lists()
        self.link_list.select_set(tk.END)
        self.on_link_select(None)
        self.modified = True

    def delete_link(self):
        sel = self.link_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if not messagebox.askyesno("Delete", f"Delete link #{idx}?"):
            return
        self.raw['linkDataArray'].pop(idx)
        self.populate_lists()
        self.modified = True

    def move_item(self, listbox, delta):
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if listbox is self.node_list:
            arr = self.raw.setdefault('nodeDataArray', [])
        else:
            arr = self.raw.setdefault('linkDataArray', [])
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(arr):
            return
        arr[idx], arr[new_idx] = arr[new_idx], arr[idx]
        self.populate_lists()
        listbox.select_set(new_idx)
        self.modified = True

    def _next_free_key(self):
        keys = [n.get('key') for n in self.raw.get('nodeDataArray', []) if 'key' in n]
        ints = [k for k in keys if isinstance(k, int)]
        base = -100
        while base in ints:
            base -= 1
        return base

    def save_json(self):
        # produce ordered arrays
        out = copy.deepcopy(self.raw)
        out['nodeDataArray'] = [reorder_node(n) for n in out.get('nodeDataArray', [])]
        out['linkDataArray'] = [reorder_link(l) for l in out.get('linkDataArray', [])]
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
            self.last_mtime = os.path.getmtime(self.json_path)
            self.modified = False
            self.set_status("Saved")
            self.update_json_textbox()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON: {e}")

    def manual_reload(self):
        if self.modified:
            if not messagebox.askyesno("Reload", "You have unsaved changes. Reloading will discard them. Continue?"):
                return
        self.load_json()

    def update_json_textbox(self):
        try:
            out = copy.deepcopy(self.raw)
            out['nodeDataArray'] = [reorder_node(n) for n in out.get('nodeDataArray', [])]
            out['linkDataArray'] = [reorder_link(l) for l in out.get('linkDataArray', [])]
            s = json.dumps(out, indent=2, ensure_ascii=False)
        except Exception as e:
            s = f"// Error serializing JSON: {e}\n{repr(self.raw)}"
        self.raw_text.delete('1.0', tk.END)
        self.raw_text.insert('1.0', s)

    def copy_json(self):
        self.update_json_textbox()
        try:
            self.clipboard_clear()
            self.clipboard_append(self.raw_text.get('1.0', 'end-1c'))
            self.set_status("JSON copied to clipboard")
        except Exception as e:
            messagebox.showerror("Clipboard", f"Failed to copy to clipboard: {e}")

    def apply_json_textbox(self):
        txt = self.raw_text.get('1.0', 'end-1c')
        try:
            parsed = json.loads(txt)
        except Exception as e:
            messagebox.showerror("Invalid JSON", f"Failed to parse JSON: {e}")
            return
        self.raw = parsed
        self.populate_lists()
        self.modified = True
        self.set_status("Applied JSON from textbox (unsaved)")

    def paste_and_apply(self):
        try:
            txt = self.clipboard_get()
        except Exception as e:
            messagebox.showerror("Clipboard", f"Failed to read clipboard: {e}")
            return
        try:
            parsed = json.loads(txt)
        except Exception as e:
            messagebox.showerror("Invalid JSON", f"Clipboard does not contain valid JSON: {e}")
            return
        self.raw = parsed
        self.populate_lists()
        self.update_json_textbox()
        self.modified = True
        self.set_status("Applied JSON from clipboard (unsaved)")

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Open JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.json_path) if os.path.exists(self.json_path) else os.path.expanduser("~")
        )
        if path:
            if self.modified:
                if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Switch file anyway?"):
                    return
            self.json_path = path
            self.file_label.config(text=os.path.basename(self.json_path))
            self.last_mtime = None
            self.load_json()
            self.set_status(f"Switched to {os.path.basename(self.json_path)}")

    def apply_offset(self):
        sel = self.node_list.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select one or more nodes first")
            return
        try:
            ox = float(self.offset_x.get())
            oy = float(self.offset_y.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "X and Y offset must be numbers")
            return
        
        nodes = self.raw.get('nodeDataArray', [])
        for idx in sel:
            node = nodes[idx]
            loc_str = node.get('location', "0 0")
            try:
                parts = loc_str.split()
                x, y = float(parts[0]), float(parts[1])
                x += ox
                y += oy
                node['location'] = f"{x} {y}"
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse location for node {idx}: {e}")
                return
        
        self.modified = True
        self.populate_lists()
        self.update_json_textbox()
        self.set_status(f"Applied offset ({ox}, {oy}) to {len(sel)} node(s)")

    def poll_file(self):
        try:
            if os.path.exists(self.json_path):
                m = os.path.getmtime(self.json_path)
                if self.last_mtime is None:
                    self.last_mtime = m
                elif m != self.last_mtime:
                    # file changed externally
                    if self.modified:
                        # ask user
                        if messagebox.askyesno("File changed", "JSON file changed on disk. Reload and discard unsaved changes? "):
                            self.load_json()
                        else:
                            # keep current and update last_mtime so we don't keep prompting
                            self.last_mtime = m
                    else:
                        self.load_json()
            else:
                self.set_status("JSON file not found")
        except Exception as e:
            print("Poll error:", e)
        self.after(POLL_INTERVAL_MS, self.poll_file)


if __name__ == '__main__':
    app = GrafcetEditor(JSON_PATH)
    app.mainloop()
