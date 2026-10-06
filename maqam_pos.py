
import base64, re
import sqlite3, csv, shutil, webbrowser, os, random
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

APP = "مقام للألبسة الرجالية"
SHOP = "مقام"

# مسارات آمنة عند تثبيت التطبيق كنظام Windows:
# الموارد تأتي من مجلد التطبيق، أما قاعدة البيانات فتُحفظ في AppData
# حتى لا تحتاج صلاحيات Administrator ولا تضيع البيانات عند تحديث البرنامج.
BASE_DIR = Path(__file__).resolve().parent
APPDATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "MaqamPOS"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)
DB = APPDATA_DIR / "maqam_pos.db"

def resource_path(name):
    """إرجاع مسار الموارد سواء شُغّل البرنامج من Python أو PyInstaller."""
    try:
        root = Path(__file__).resolve().parent
    except Exception:
        root = Path.cwd()
    return root / name


# ---------- BARCODE HELPERS ----------
_CODE39 = {
    "0":"nnnwwnwnn","1":"wnnwnnnnw","2":"nnwwnnnnw","3":"wnwwnnnnn",
    "4":"nnnwwnnnw","5":"wnnwwnnnn","6":"nnwwwnnnn","7":"nnnwnnwnw",
    "8":"wnnwnnwnn","9":"nnwwnnwnn","A":"wnnnnwnnw","B":"nnwnnwnnw",
    "C":"wnwnnwnnn","D":"nnnnwwnnw","E":"wnnnwwnnn","F":"nnwnwwnnn",
    "G":"nnnnnwwnw","H":"wnnnnwwnn","I":"nnwnnwwnn","J":"nnnnwwwnn",
    "K":"wnnnnnnww","L":"nnwnnnnww","M":"wnwnnnnwn","N":"nnnnwnnww",
    "O":"wnnnwnnwn","P":"nnwnwnnwn","Q":"nnnnnnwww","R":"wnnnnnwwn",
    "S":"nnwnnnwwn","T":"nnnnwnwwn","U":"wwnnnnnnw","V":"nwwnnnnnw",
    "W":"wwwnnnnnn","X":"nwwnnnnwn","Y":"wwwnnnnwn","Z":"nwwwnnnnn",
    "-":"nwnnnnwnw",".":"wwnnnnwnn"," ":"" ,"$":"nwnwnwnnn","/":"nwnwnnnwn",
    "+":"nwnnnwnwn","%":"nnnwnwnwn","*":"nwnnwnwnn"
}
def code39_svg(value, height=74, narrow=3, wide=7):
    value=str(value).upper()
    payload="*"+value+"*"
    if any(ch not in _CODE39 or not _CODE39[ch] for ch in payload):
        value=re.sub(r"[^0-9A-Z .\\-$/+%]","",value)
        payload="*"+value+"*"
    x=0; bars=[]; gap=1
    for idx,ch in enumerate(payload):
        pattern=_CODE39[ch]
        for j,w in enumerate(pattern):
            width=wide if w=="w" else narrow
            if j%2==0:
                bars.append(f'<rect x="{x}" y="0" width="{width}" height="{height}" fill="#000"/>')
            x += width
        x += gap
    width=x+2
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height+24}" viewBox="0 0 {width} {height+24}" role="img" aria-label="Barcode {value}"><rect width="100%" height="100%" fill="#fff"/>{ "".join(bars) }<text x="{width/2}" y="{height+18}" text-anchor="middle" font-family="Arial" font-size="14">{value}</text></svg>'

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        color TEXT, size TEXT, buy REAL DEFAULT 0,
        sell REAL DEFAULT 0, qty INTEGER DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sale_no TEXT UNIQUE,
        sale_time TEXT, total REAL, paid REAL, change_amt REAL, profit REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS sale_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER,
        barcode TEXT, name TEXT, color TEXT, size TEXT,
        qty INTEGER, price REAL, cost REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_time TEXT, note TEXT, amount REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS stock_moves(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        move_time TEXT, barcode TEXT, move_type TEXT,
        qty INTEGER, note TEXT, ref TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sales_time ON sales(sale_time)")
    con.execute("CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,phone TEXT,note TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_no TEXT UNIQUE,purchase_time TEXT,supplier TEXT,total REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_id INTEGER,barcode TEXT,name TEXT,color TEXT,size TEXT,qty INTEGER,cost REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT UNIQUE,note TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS options(
        kind TEXT, value TEXT, UNIQUE(kind,value))""")
    con.execute("""CREATE TABLE IF NOT EXISTS returns(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, sale_no TEXT,
        return_time TEXT, total REAL DEFAULT 0, note TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS return_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, return_id INTEGER, sale_item_id INTEGER,
        barcode TEXT, name TEXT, color TEXT, size TEXT, qty INTEGER,
        price REAL, cost REAL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_returns_sale_no ON returns(sale_no)")
    con.commit()
    return con

def money(x): return f"{float(x):,.2f}"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        # شعار التطبيق (يظهر في نافذة البرنامج وشريط المهام)
        try:
            self._app_icon = tk.PhotoImage(file=str(resource_path("maqam_logo.png")))
            self.iconphoto(True, self._app_icon)
        except Exception:
            self._app_icon = None
        self.geometry("1280x720")
        self.minsize(1100, 650)
        self.minsize(1200,700)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.configure(bg="#111111")
        self.cart=[]
        self.invoice_no=None
        self._style()
        self.build()

    def _style(self):
        s=ttk.Style(self)
        try: s.theme_use("clam")
        except: pass
        s.configure("TNotebook", background="#111111", borderwidth=0)
        s.configure("TNotebook.Tab", padding=[8,5], font=("Segoe UI",9,"bold"),
                    background="#181818", foreground="#d8b56a")
        s.map("TNotebook.Tab", background=[("selected","#2A2415"),("active","#211E17")],
        foreground=[("selected","#F0C95C"),("active","#F0C95C")])
        s.configure("Treeview", rowheight=28, font=("Segoe UI",9))
        s.configure("Treeview.Heading", font=("Segoe UI",10,"bold"))
        s.configure("TButton", font=("Segoe UI",9,"bold"), padding=4)
        s.configure("Small.TButton", font=("Segoe UI",8,"bold"), padding=[3,2])
        s.configure("Return.TButton", font=("Segoe UI",10,"bold"), padding=[6,4])
        s.configure("Title.TLabel", background="#111111", foreground="#d8b56a",
                    font=("Segoe UI",23,"bold"))
        s.configure("Sub.TLabel", background="#111111", foreground="#eeeeee",
                    font=("Segoe UI",11))
        s.configure("Card.TLabel", background="#f5f1e8", foreground="#222",
                    font=("Segoe UI",15,"bold"), padding=18)

    def section_header(self, parent, title):
        bar = tk.Frame(parent, bg="#111111", height=78)
        bar.pack(fill="x", pady=(0,10))
        bar.pack_propagate(False)
        tk.Label(bar, text="مـقـام", bg="#111111", fg="#D4AF37",
                 font=("Georgia", 20, "bold")).pack(pady=(4,0))
        tk.Label(bar, text=title, bg="#111111", fg="#F2F2F2",
                 font=("Segoe UI", 9, "bold")).pack(pady=(0,6))
        tk.Frame(parent, bg="#D4AF37", height=2).pack(fill="x", pady=(0,8))

    def build(self):
        top=tk.Frame(self,bg="#111111",height=65); top.pack(fill="x")
        ttk.Label(top,text="مَقَام",style="Title.TLabel").pack(side="right",padx=25,pady=6)
        ttk.Label(top,text=f"{APP}  |  {SHOP}",style="Sub.TLabel").pack(side="right",pady=18)
        self.nb=ttk.Notebook(self); self.nb.pack(fill="both",expand=True,padx=8,pady=5)
        self.sales_tab(); self.inventory_tab(); self.products_tab()
        self.stocktake_tab(); self.sales_history_tab(); self.returns_tab(); self.purchases_tab(); self.suppliers_tab(); self.customers_tab(); self.expenses_tab(); self.reports_tab(); self.settings_tab()

    # ---------- SALES ----------
    def sales_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="🛒 المبيعات")
        self.section_header(f, "المبيعات")
        left=ttk.Frame(f); left.pack(side="left",fill="both",expand=True,padx=(0,10))
        right=ttk.Frame(f,width=320); right.pack(side="right",fill="y")
        ttk.Label(left,text="سلة البيع",font=("Segoe UI",13,"bold")).pack(anchor="e")
        cols=("barcode","name","color","size","qty","price","total")
        self.carttv=ttk.Treeview(left,columns=cols,show="headings")
        heads={"barcode":"الباركود","name":"المنتج","color":"اللون","size":"القياس",
               "qty":"الكمية","price":"السعر","total":"الإجمالي"}
        widths={"barcode":150,"name":230,"color":120,"size":100,"qty":75,"price":110,"total":125}
        for c in cols:
            self.carttv.heading(c,text=heads[c]); self.carttv.column(c,width=widths[c],anchor="center")
        self.carttv.pack(fill="both",expand=True,pady=10)

        ttk.Label(right,text="مسح الباركود",font=("Segoe UI",9,"bold")).pack(anchor="e")
        self.scan=tk.StringVar()
        e=ttk.Entry(right,textvariable=self.scan,font=("Segoe UI",10)); e.pack(fill="x",pady=4)
        e.bind("<Return>",lambda x:self.add_scan())
        ttk.Button(right,text="إضافة بالباركود",command=self.add_scan,style="Small.TButton").pack(fill="x",pady=2)
        ttk.Button(right,text="حذف المحدد",command=self.remove_cart,style="Small.TButton").pack(fill="x",pady=2)
        ttk.Button(right,text="💰 سعر خاص / لصديق",command=self.special_price,style="Small.TButton").pack(fill="x",pady=2)
        ttk.Button(right,text="تفريغ السلة",command=self.clear_cart,style="Small.TButton").pack(fill="x",pady=2)

        self.total_lbl=ttk.Label(right,text="الإجمالي: 0.00",font=("Segoe UI",11,"bold"))
        self.total_lbl.pack(anchor="e",pady=10)
        ttk.Label(right,text="المبلغ المدفوع",font=("Segoe UI",10,"bold")).pack(anchor="e")
        self.paid=tk.StringVar(value="0")
        pe=ttk.Entry(right,textvariable=self.paid,font=("Segoe UI",13)); pe.pack(fill="x",pady=4)
        pe.bind("<KeyRelease>",lambda e:self.update_payment())
        self.change_lbl=ttk.Label(right,text="الباقي: 0.00",font=("Segoe UI",11,"bold"))
        self.change_lbl.pack(anchor="e",pady=5)
        self.complete_btn=ttk.Button(right,text="✓ إتمام البيع + إصدار الفاتورة",command=self.complete_sale)
        self.complete_btn.pack(fill="x",pady=(3,5),ipady=2)
        self.bind("<Control-Return>",lambda e:self.complete_sale())

    def add_scan(self):
        code=self.scan.get().strip()
        if not code: return
        con=db(); p=con.execute("SELECT * FROM products WHERE barcode=?",(code,)).fetchone(); con.close()
        if not p:
            self.scan.focus_set()
            messagebox.showwarning("غير موجود",f"الباركود {code} غير موجود. أضف المنتج أولاً من تبويب البضاعة.")
            return
        existing=next((x for x in self.cart if x["barcode"]==code),None)
        current=existing["qty"] if existing else 0
        if current+1 > p["qty"]:
            messagebox.showwarning("المخزون",f"المتوفر من {p['name']} هو {p['qty']} قطعة فقط.")
            return
        if existing: existing["qty"]+=1
        else:
            self.cart.append(dict(barcode=p["barcode"],name=p["name"],color=p["color"] or "",
                                  size=p["size"] or "",qty=1,price=p["sell"],base_price=p["sell"],cost=p["buy"]))
        self.scan.set(""); self.refresh_cart(); self.scan.focus_set()

    def special_price(self):
        """Apply a one-sale special price without changing the product's stored sell price."""
        sel=self.carttv.selection()
        if not sel:
            messagebox.showinfo("السعر الخاص","حدد القطعة من سلة البيع أولاً.")
            return
        idx=self.carttv.index(sel[0])
        if idx < 0 or idx >= len(self.cart): return
        item=self.cart[idx]
        base=float(item.get("base_price", item["price"]))
        value=simpledialog.askstring(
            "سعر خاص",
            f"السعر الأساسي: {money(base)}\nأدخل سعر البيع الخاص لهذه الفاتورة فقط:",
            parent=self
        )
        if value is None: return
        value=value.strip().replace(",", ".")
        try:
            special=float(value)
        except ValueError:
            messagebox.showerror("سعر غير صحيح","أدخل رقمًا صحيحًا للسعر.")
            return
        if special < 0:
            messagebox.showerror("سعر غير صحيح","السعر لا يمكن أن يكون سالبًا.")
            return
        item["price"]=special
        item["special_price"]=True
        self.refresh_cart()
        self.carttv.selection_set(sel[0])
        self.carttv.focus(sel[0])

    def refresh_cart(self):
        for i in self.carttv.get_children(): self.carttv.delete(i)
        total=0
        for x in self.cart:
            t=x["qty"]*x["price"]; total+=t
            self.carttv.insert("", "end", values=(x["barcode"],x["name"],x["color"],x["size"],
                                                  x["qty"],money(x["price"]),money(t)))
        self.total_lbl.config(text=f"الإجمالي: {money(total)}")
        self.update_payment()

    def update_payment(self):
        try: paid=float(self.paid.get() or 0)
        except: paid=0
        total=sum(x["qty"]*x["price"] for x in self.cart)
        diff=paid-total
        self.change_lbl.config(text=("الباقي: " if diff>=0 else "المتبقي: ")+money(abs(diff)))

    def remove_cart(self):
        sel=self.carttv.selection()
        if not sel: return
        idx=self.carttv.index(sel[0]); self.cart.pop(idx); self.refresh_cart()

    def clear_cart(self):
        self.cart=[]; self.paid.set("0"); self.refresh_cart()

    def complete_sale(self):
        if not self.cart:
            messagebox.showwarning("السلة فارغة","أضف منتجات أولاً."); return
        total=sum(x["qty"]*x["price"] for x in self.cart)
        try: paid=float(self.paid.get() or 0)
        except:
            messagebox.showerror("خطأ","المبلغ المدفوع غير صحيح."); return
        if paid < total:
            messagebox.showwarning("المبلغ","المبلغ المدفوع أقل من الإجمالي."); return
        sale_no=datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        change=paid-total
        profit=sum(x["qty"]*(x["price"]-x["cost"]) for x in self.cart)
        con=db(); cur=con.cursor()
        try:
            for x in self.cart:
                row=cur.execute("SELECT qty FROM products WHERE barcode=?",(x["barcode"],)).fetchone()
                if not row or row["qty"] < x["qty"]:
                    raise ValueError(f"المخزون غير كافٍ للمنتج {x['name']} ({x['barcode']})")
            cur.execute("INSERT INTO sales(sale_no,sale_time,total,paid,change_amt,profit) VALUES(?,?,?,?,?,?)",
                        (sale_no,datetime.now().isoformat(timespec="seconds"),total,paid,change,profit))
            sid=cur.lastrowid
            for x in self.cart:
                cur.execute("UPDATE products SET qty=qty-? WHERE barcode=?",(x["qty"],x["barcode"]))
                cur.execute("""INSERT INTO sale_items(sale_id,barcode,name,color,size,qty,price,cost)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (sid,x["barcode"],x["name"],x["color"],x["size"],x["qty"],x["price"],x["cost"]))
                cur.execute("INSERT INTO stock_moves(move_time,barcode,move_type,qty,note,ref) VALUES(?,?,?,?,?,?)",
                            (datetime.now().isoformat(timespec="seconds"),x["barcode"],"بيع",-x["qty"],"بيع من الكاشير",sale_no))
            con.commit()
        except Exception as e:
            con.rollback(); con.close(); messagebox.showerror("تعذر إتمام البيع",str(e)); return
        con.close()
        self.invoice_no=sale_no
        self.make_invoice_html(sale_no,total,paid,change,self.cart)
        messagebox.showinfo("تم البيع",f"تم حفظ الفاتورة رقم {sale_no}\nالباقي: {money(change)}")
        self.clear_cart(); self.refresh_inventory(); self.refresh_reports(); self.refresh_sales_history()
        if messagebox.askyesno("الفاتورة","هل تريد فتح الفاتورة للطباعة الآن?"):
            webbrowser.open(str(self.invoice_path))

    def make_invoice_html(self,sale_no,total,paid,change,items):
        rows=""
        for i,x in enumerate(items,1):
            rows += f"<tr><td>{i}</td><td>{x['name']}</td><td>{x['color']}</td><td>{x['size']}</td><td>{x['qty']}</td><td>{money(x['price'])}</td><td>{money(x['qty']*x['price'])}</td></tr>"
        logo_path = resource_path("maqam_logo_watermark.png")
        logo_uri = ""
        if logo_path.exists():
            try:
                logo_uri = "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode("ascii")
            except Exception:
                logo_uri = ""
        logo_html = f'<img class="logo" src="{logo_uri}" alt="مقام">' if logo_uri else ''
        html=f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">
        <title>فاتورة {sale_no}</title>
        <style>
        body{{font-family:Arial,sans-serif;width:760px;margin:25px auto;color:#111;background:#fff;position:relative}}
        .invoice{{position:relative;min-height:850px}}
        .head{{text-align:center;border:2px solid #D4AF37;padding:14px 10px 12px;border-radius:8px;position:relative;z-index:2;background:rgba(255,255,255,.94)}}
        .head h1{{margin:0;color:#111;font-size:30px}} .head .sub{{font-size:14px;color:#555;margin-top:4px}}
        .watermark{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:330px;height:300px;display:flex;align-items:center;justify-content:center;opacity:.13;pointer-events:none;z-index:-1}}
        .watermark img{{width:230px;height:280px;object-fit:contain}}
        .meta{{position:relative;z-index:2;margin-top:12px;font-size:14px}}
        table{{width:100%;border-collapse:collapse;margin-top:18px;position:relative;z-index:2;background:rgba(255,255,255,.94)}}
        th{{background:#111;color:#D4AF37}} th,td{{border:1px solid #bbb;padding:8px;text-align:center}}
        .sum{{margin-top:18px;font-size:17px;line-height:1.9;border-top:2px solid #D4AF37;padding-top:10px;position:relative;z-index:2;background:rgba(255,255,255,.94)}}
        .sum .total{{font-size:20px;font-weight:bold}} .no-profit-note{{display:none}}
        .invoice-barcode{{clear:both;text-align:center;margin-top:30px;position:relative;z-index:3;background:#fff;padding:12px 10px 16px;border-top:1px solid #eee}}
        .invoice-barcode svg{{max-width:100%;height:auto}}
        button{{margin-top:16px;padding:10px 22px;background:#111;color:#D4AF37;border:1px solid #D4AF37;border-radius:5px;font-weight:bold;position:relative;z-index:3}}
        @media print{{button{{display:none}} body{{margin:0 auto}} .watermark{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:-1}}}}
        /* MAQAM_WATERMARK_CSS */

<style>
.watermark {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    opacity: 0.08;
    z-index: 0;
}
.watermark img {
    max-width: 55%;
    max-height: 55%;
    object-fit: contain;
}
.invoice .head,
.invoice > *:not(.watermark) {
    position: relative;
    z-index: 1;
}
</style>

</style>
        <div class="invoice">
          <div class="watermark">{logo_html}</div>
          <div class="head">
            <h1>{SHOP}</h1>
            <div class="sub">فاتورة مبيعات</div>
            <div class="meta">رقم الفاتورة: <b>{sale_no}</b><br>{datetime.now():%Y-%m-%d %H:%M}</div>
          </div>
          <table><tr><th>#</th><th>المنتج</th><th>اللون</th><th>القياس</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr>{rows}</table>
          <div class="sum"><div class="total">الإجمالي: {money(total)}</div>المدفوع: {money(paid)}<br>الباقي: {money(change)}</div>
          <div class="invoice-barcode"><div>باركود الفاتورة</div>{code39_svg(sale_no)}</div>
          <button onclick="window.print()">طباعة الفاتورة</button>
        </div>
        </html>"""
        invoice_dir=APPDATA_DIR / "Invoices"
        invoice_dir.mkdir(parents=True,exist_ok=True)
        p=invoice_dir / f"فاتورة_{sale_no}.html"
        p.write_text(html,encoding="utf-8"); self.invoice_path=p

    # ---------- INVENTORY ----------
    def inventory_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="📦 المخزون")
        self.section_header(f, "المخزون")
        bar=ttk.Frame(f); bar.pack(fill="x",pady=5)
        self.inv_search=tk.StringVar()
        ttk.Entry(bar,textvariable=self.inv_search).pack(side="right",fill="x",expand=True,padx=5)
        ttk.Button(bar,text="بحث",command=self.refresh_inventory).pack(side="right")
        cols=("barcode","name","color","size","buy","sell","qty","value")
        self.invtv=ttk.Treeview(f,columns=cols,show="headings")
        heads={"barcode":"الباركود","name":"المنتج","color":"اللون","size":"القياس",
               "buy":"الشراء","sell":"البيع","qty":"الكمية","value":"قيمة المخزون"}
        for c in cols:
            self.invtv.heading(c,text=heads[c]); self.invtv.column(c,width=125,anchor="center")
        self.invtv.pack(fill="both",expand=True,pady=8); self.refresh_inventory()

    def refresh_inventory(self):
        if not hasattr(self,"invtv"): return
        for i in self.invtv.get_children(): self.invtv.delete(i)
        q=self.inv_search.get().strip() if hasattr(self,"inv_search") else ""
        con=db(); rows=con.execute("""SELECT * FROM products WHERE barcode LIKE ? OR name LIKE ? OR color LIKE ? OR size LIKE ?
                                      ORDER BY name""",(f"%{q}%",)*4).fetchall(); con.close()
        for p in rows:
            self.invtv.insert("", "end", values=(p["barcode"],p["name"],p["color"] or "",p["size"] or "",
                                                 money(p["buy"]),money(p["sell"]),p["qty"],money(p["buy"]*p["qty"])))

    # ---------- PRODUCT / VARIANTS ----------
    def products_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="➕ البضاعة والمقاسات")
        self.section_header(f, "البضاعة والمقاسات")
        self.vars={}
        fields=[("barcode","الباركود"),("name","اسم المنتج"),("color","اللون"),
                ("size","القياس"),("buy","سعر الشراء"),("sell","سعر البيع"),("qty","الكمية")]
        form=ttk.Frame(f); form.pack(fill="x",pady=15)
        for i,(key,label) in enumerate(fields):
            ttk.Label(form,text=label).grid(row=i,column=1,sticky="e",padx=10,pady=5)
            v=tk.StringVar(); self.vars[key]=v
            ent=ttk.Entry(form,textvariable=v,width=38)
            ent.grid(row=i,column=0,sticky="w",padx=10,pady=5)
            if key=="barcode":
                self.product_barcode_entry=ent
                ent.bind("<Return>", lambda e: self.barcode_product_enter())
        buttons=ttk.Frame(f); buttons.pack(pady=8)
        ttk.Button(buttons,text="حفظ / تحديث",command=self.save_product).pack(side="right",padx=5)
        ttk.Button(buttons,text="مسح الحقول",command=self.clear_product_form).pack(side="right",padx=5)
        ttk.Button(buttons,text="🗑️ حذف المنتج نهائيًا",command=self.delete_product).pack(side="right",padx=5)
        ttk.Button(buttons,text="إدارة الألوان والمقاسات",command=self.manage_options).pack(side="right",padx=5)
        ttk.Label(f,text="كل لون/قياس يمكن أن يكون له باركود مستقل. عند إدخال كمية لنفس الباركود، تضاف إلى المخزون.",
                  foreground="#666").pack(pady=15)

    def barcode_product_enter(self):
        code=self.vars["barcode"].get().strip()
        if not code:
            return "break"
        con=db()
        p=con.execute("SELECT * FROM products WHERE barcode=?",(code,)).fetchone()
        con.close()
        if p:
            for k in ("barcode","name","color","size","buy","sell"):
                self.vars[k].set("" if p[k] is None else str(p[k]))
            self.vars["qty"].set("")
            messagebox.showinfo("الباركود موجود",f"المنتج موجود مسبقًا: {p['name']}\nأدخل كمية الإضافة ثم اضغط حفظ / تحديث.")
        else:
            messagebox.showinfo("باركود جديد",f"تم التقاط الباركود: {code}\nأكمل بيانات المنتج والكمية ثم اضغط حفظ / تحديث.")
        return "break"

    def clear_product_form(self):
        for v in self.vars.values(): v.set("")

    def save_product(self):
        try:
            code=self.vars["barcode"].get().strip(); name=self.vars["name"].get().strip()
            if not code or not name: raise ValueError()
            buy=float(self.vars["buy"].get() or 0); sell=float(self.vars["sell"].get() or 0); qty=int(self.vars["qty"].get() or 0)
            con=db(); old=con.execute("SELECT id FROM products WHERE barcode=?",(code,)).fetchone()
            if old:
                con.execute("""UPDATE products SET name=?,color=?,size=?,buy=?,sell=?,qty=qty+? WHERE barcode=?""",
                            (name,self.vars["color"].get(),self.vars["size"].get(),buy,sell,qty,code))
            else:
                con.execute("""INSERT INTO products(barcode,name,color,size,buy,sell,qty) VALUES(?,?,?,?,?,?,?)""",
                            (code,name,self.vars["color"].get(),self.vars["size"].get(),buy,sell,qty))
            if qty:
                con.execute("INSERT INTO stock_moves(move_time,barcode,move_type,qty,note,ref) VALUES(?,?,?,?,?,?)",
                            (datetime.now().isoformat(timespec="seconds"),code,"إضافة",qty,"إضافة/تحديث مخزون",""))
            con.commit(); con.close()
            messagebox.showinfo("تم",f"تم حفظ المنتج. تمت إضافة {qty} قطعة للمخزون."); self.refresh_inventory(); self.refresh_stocktake(); self.clear_product_form()
        except Exception as e:
            messagebox.showerror("خطأ","تأكد من البيانات والأسعار والكمية.")

    def delete_product(self):
        code=self.vars["barcode"].get().strip()
        if not code:
            messagebox.showwarning("حذف المنتج", "أدخل أو امسح باركود المنتج أولًا.")
            return
        con=db(); p=con.execute("SELECT * FROM products WHERE barcode=?",(code,)).fetchone(); con.close()
        if not p:
            messagebox.showwarning("حذف المنتج", "لم يتم العثور على منتج بهذا الباركود.")
            return
        ok=messagebox.askyesno("تأكيد الحذف النهائي",
            f"هل أنت متأكد من حذف المنتج نهائيًا؟\n\nالمنتج: {p['name']}\nالباركود: {p['barcode']}\nالكمية الحالية: {p['qty']}\n\nلا يمكن التراجع عن هذا الحذف.")
        if not ok: return
        try:
            con=db(); con.execute("DELETE FROM products WHERE barcode=?",(code,)); con.commit(); con.close()
            self.clear_product_form(); self.refresh_inventory(); self.refresh_stocktake(); self.refresh_reports()
            messagebox.showinfo("تم الحذف", "تم حذف المنتج نهائيًا من المخزون.")
        except Exception as e:
            try: con.close()
            except Exception: pass
            messagebox.showerror("خطأ", f"تعذر حذف المنتج: {e}")

    def manage_options(self):
        w=tk.Toplevel(self); w.title("إدارة الألوان والمقاسات"); w.geometry("720x470")
        for col,kind,title in [(0,"color","الألوان"),(1,"size","المقاسات")]:
            frame=ttk.LabelFrame(w,text=title,padding=10); frame.grid(row=0,column=col,sticky="nsew",padx=10,pady=10)
            w.grid_columnconfigure(col,weight=1)
            ent=tk.StringVar(); ttk.Entry(frame,textvariable=ent).pack(fill="x",pady=5)
            tv=ttk.Treeview(frame,columns=("v",),show="headings",height=9); tv.heading("v",text=title); tv.pack(fill="both",expand=True,pady=5)
            def refresh(tv=tv,kind=kind):
                for i in tv.get_children(): tv.delete(i)
                con=db(); rs=con.execute("SELECT value FROM options WHERE kind=? ORDER BY value",(kind,)).fetchall(); con.close()
                for r in rs: tv.insert("", "end", values=(r["value"],))
            def add(ent=ent,kind=kind,tv=tv):
                v=ent.get().strip()
                if not v: return
                try:
                    con=db(); con.execute("INSERT OR IGNORE INTO options(kind,value) VALUES(?,?)",(kind,v)); con.commit(); con.close()
                    ent.set(""); refresh(tv,kind)
                except: pass
            def delete(tv=tv,kind=kind):
                sel=tv.selection()
                if not sel: return
                v=tv.item(sel[0])["values"][0]
                con=db(); con.execute("DELETE FROM options WHERE kind=? AND value=?",(kind,v)); con.commit(); con.close(); refresh(tv,kind)
            ttk.Button(frame,text="إضافة",command=add).pack(side="left",padx=3)
            ttk.Button(frame,text="حذف",command=delete).pack(side="left",padx=3)
            refresh()
        ttk.Label(w,text="هذه القوائم تساعدك على توحيد المقاسات والألوان، والمنتج نفسه يحتفظ بقيمته الفعلية.",
                  foreground="#666").grid(row=1,column=0,columnspan=2,pady=10)

    # ---------- STOCKTAKE ----------
    def stocktake_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="🧮 الجرد")
        self.section_header(f, "الجرد")
        bar=ttk.Frame(f); bar.pack(fill="x",pady=5)
        self.st_search=tk.StringVar()
        ttk.Entry(bar,textvariable=self.st_search).pack(side="right",fill="x",expand=True,padx=5)
        ttk.Button(bar,text="تحميل الجرد",command=self.refresh_stocktake).pack(side="right")
        ttk.Button(bar,text="حفظ الجرد المحدد",command=self.apply_stocktake).pack(side="right",padx=5)
        cols=("barcode","name","color","size","system","counted","diff")
        self.sttv=ttk.Treeview(f,columns=cols,show="headings")
        heads={"barcode":"الباركود","name":"المنتج","color":"اللون","size":"القياس",
               "system":"رصيد النظام","counted":"العد الفعلي","diff":"الفرق"}
        for c in cols:
            self.sttv.heading(c,text=heads[c]); self.sttv.column(c,width=145,anchor="center")
        self.sttv.pack(fill="both",expand=True,pady=8)
        self.sttv.bind("<Double-1>",self.edit_counted)
        self.refresh_stocktake()

    def refresh_stocktake(self):
        if not hasattr(self,"sttv"): return
        for i in self.sttv.get_children(): self.sttv.delete(i)
        q=self.st_search.get().strip() if hasattr(self,"st_search") else ""
        con=db(); rows=con.execute("""SELECT * FROM products WHERE barcode LIKE ? OR name LIKE ? ORDER BY name""",
                                   (f"%{q}%",f"%{q}%")).fetchall(); con.close()
        for p in rows:
            self.sttv.insert("", "end", values=(p["barcode"],p["name"],p["color"] or "",p["size"] or "",p["qty"],p["qty"],0))

    def edit_counted(self,event=None):
        item=self.sttv.identify_row(event.y) if event else None
        if not item: return
        vals=list(self.sttv.item(item,"values"))
        x=tk.simpledialog.askinteger("الجرد","أدخل الكمية الفعلية:",initialvalue=int(vals[5]),minvalue=0)
        if x is not None:
            vals[5]=x; vals[6]=x-int(vals[4]); self.sttv.item(item,values=vals)

    def apply_stocktake(self):
        sel=self.sttv.selection()
        if not sel:
            messagebox.showwarning("الجرد","حدد منتجاً واحداً على الأقل بعد تعديل الكمية الفعلية."); return
        con=db()
        for item in sel:
            vals=self.sttv.item(item,"values"); code=vals[0]; counted=int(vals[5])
            con.execute("UPDATE products SET qty=? WHERE barcode=?",(counted,code))
        con.commit(); con.close(); self.refresh_stocktake(); self.refresh_inventory()
        messagebox.showinfo("تم","تم تطبيق الجرد على المنتجات المحددة.")

    # ---------- SALES HISTORY ----------
    def sales_history_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="🧾 سجل المبيعات")
        self.section_header(f, "سجل المبيعات")
        bar=ttk.Frame(f); bar.pack(fill="x",pady=5)
        self.sales_search=tk.StringVar()
        ttk.Entry(bar,textvariable=self.sales_search).pack(side="right",fill="x",expand=True,padx=5)
        ttk.Button(bar,text="بحث / تحديث",command=self.refresh_sales_history).pack(side="right")
        cols=("no","date","total","paid","change","profit")
        self.salestv=ttk.Treeview(f,columns=cols,show="headings")
        heads={"no":"رقم الفاتورة","date":"التاريخ","total":"الإجمالي","paid":"المدفوع","change":"الباقي","profit":"الربح"}
        for c in cols:
            self.salestv.heading(c,text=heads[c]); self.salestv.column(c,width=180,anchor="center")
        self.salestv.pack(fill="both",expand=True,pady=8)
        actions=ttk.Frame(f); actions.pack(fill="x",pady=5)
        ttk.Button(actions,text="🗑️ حذف الفاتورة نهائيًا",command=self.delete_sale).pack(side="right")
        ttk.Label(actions,text="الحذف النهائي يعيد الكميات غير المرتجعة إلى المخزون.",foreground="#777").pack(side="right",padx=12)
        self.salestv.bind("<Double-1>",self.show_sale_details)
        self.refresh_sales_history()

    def refresh_sales_history(self):
        if not hasattr(self,"salestv"): return
        for i in self.salestv.get_children(): self.salestv.delete(i)
        q=self.sales_search.get().strip() if hasattr(self,"sales_search") else ""
        con=db(); rows=con.execute("""SELECT * FROM sales WHERE sale_no LIKE ? OR sale_time LIKE ? ORDER BY id DESC LIMIT 300""",
                                   (f"%{q}%",f"%{q}%")).fetchall(); con.close()
        for r in rows:
            self.salestv.insert("","end",values=(r["sale_no"],r["sale_time"],money(r["total"]),money(r["paid"]),money(r["change_amt"]),money(r["profit"])),iid=str(r["id"]))

    def delete_sale(self):
        sel=self.salestv.selection()
        if not sel:
            messagebox.showwarning("حذف الفاتورة", "حدد الفاتورة التي تريد حذفها أولًا.")
            return
        sid=int(sel[0])
        con=db(); sale=con.execute("SELECT * FROM sales WHERE id=?",(sid,)).fetchone()
        if not sale:
            con.close(); return
        ok=messagebox.askyesno("تأكيد الحذف النهائي",
            f"هل أنت متأكد من حذف الفاتورة نهائيًا؟\n\nرقم الفاتورة: {sale['sale_no']}\nالإجمالي: {money(sale['total'])}\n\nسيتم حذف الفاتورة وبنودها نهائيًا، وإعادة الكميات التي لم يتم إرجاعها إلى المخزون.\nلا يمكن التراجع عن هذا الحذف.")
        if not ok:
            con.close(); return
        try:
            con.execute("BEGIN")
            items=con.execute("SELECT * FROM sale_items WHERE sale_id=?",(sid,)).fetchall()
            for item in items:
                returned=con.execute("SELECT COALESCE(SUM(qty),0) q FROM return_items WHERE sale_item_id=?",(item['id'],)).fetchone()['q']
                net=max(0,int(item['qty'])-int(returned or 0))
                if net:
                    prod=con.execute("SELECT id FROM products WHERE barcode=?",(item['barcode'],)).fetchone()
                    if prod:
                        con.execute("UPDATE products SET qty=qty+? WHERE barcode=?",(net,item['barcode']))
                    else:
                        con.execute("INSERT INTO products(barcode,name,color,size,buy,sell,qty) VALUES(?,?,?,?,?,?,?)",
                                     (item['barcode'],item['name'],item['color'],item['size'],item['cost'],item['price'],net))
            con.execute("DELETE FROM return_items WHERE return_id IN (SELECT id FROM returns WHERE sale_id=?)",(sid,))
            con.execute("DELETE FROM returns WHERE sale_id=?",(sid,))
            con.execute("DELETE FROM sale_items WHERE sale_id=?",(sid,))
            con.execute("DELETE FROM sales WHERE id=?",(sid,))
            con.commit(); con.close()
            self.refresh_sales_history(); self.refresh_inventory(); self.refresh_stocktake(); self.refresh_reports()
            messagebox.showinfo("تم الحذف", f"تم حذف الفاتورة {sale['sale_no']} نهائيًا وإعادة الكمية غير المرتجعة إلى المخزون.")
        except Exception as e:
            try: con.rollback(); con.close()
            except Exception: pass
            messagebox.showerror("خطأ", f"تعذر حذف الفاتورة: {e}")

    def show_sale_details(self,event=None):
        sel=self.salestv.selection()
        if not sel:return
        sid=int(sel[0]); con=db()
        sale=con.execute("SELECT * FROM sales WHERE id=?",(sid,)).fetchone()
        items=con.execute("SELECT * FROM sale_items WHERE sale_id=?",(sid,)).fetchall(); con.close()
        w=tk.Toplevel(self); w.title(f"تفاصيل الفاتورة {sale['sale_no']}"); w.geometry("900x520")
        ttk.Label(w,text=f"الفاتورة {sale['sale_no']} — الإجمالي {money(sale['total'])}",font=("Segoe UI",15,"bold")).pack(anchor="e",padx=15,pady=10)
        tv=ttk.Treeview(w,columns=("barcode","name","color","size","qty","price","total"),show="headings")
        for c,h in [("barcode","الباركود"),("name","المنتج"),("color","اللون"),("size","القياس"),("qty","الكمية"),("price","السعر"),("total","الإجمالي")]:
            tv.heading(c,text=h); tv.column(c,width=115,anchor="center")
        tv.pack(fill="both",expand=True,padx=10,pady=10)
        for x in items: tv.insert("","end",values=(x["barcode"],x["name"],x["color"],x["size"],x["qty"],money(x["price"]),money(x["qty"]*x["price"])))

    # ---------- RETURNS ----------
    def returns_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="↩️ المرتجعات")
        self.section_header(f, "المرتجعات والاستبدال")
        top=ttk.Frame(f); top.pack(fill="x",pady=6)
        ttk.Label(top,text="رقم الفاتورة",font=("Segoe UI",9,"bold")).pack(side="right",padx=6)
        self.return_search=tk.StringVar()
        ent=ttk.Entry(top,textvariable=self.return_search,font=("Segoe UI",14))
        ent.pack(side="right",fill="x",expand=True,padx=6)
        ent.bind("<Return>",lambda e:self.find_return_invoice())
        ttk.Button(top,text="🔎 بحث عن الفاتورة",command=self.find_return_invoice).pack(side="right",padx=4)
        ttk.Button(top,text="مسح",command=self.clear_return_view).pack(side="right",padx=4)
        self.return_info=ttk.Label(f,text="أدخل رقم الفاتورة ثم اضغط بحث.",font=("Segoe UI",12,"bold"))
        self.return_info.pack(anchor="e",pady=8)
        cols=("item_id","barcode","name","color","size","sold","returned","available","price","return_qty")
        self.return_tv=ttk.Treeview(f,columns=cols,show="headings",height=12)
        heads={"item_id":"رقم البند","barcode":"الباركود","name":"المنتج","color":"اللون","size":"القياس",
               "sold":"المباع","returned":"المرتجع","available":"المتاح للإرجاع","price":"السعر","return_qty":"كمية الإرجاع"}
        widths={"item_id":85,"barcode":150,"name":240,"color":110,"size":90,"sold":85,"returned":95,"available":120,"price":110,"return_qty":120}
        for c in cols:
            self.return_tv.heading(c,text=heads[c]); self.return_tv.column(c,width=widths[c],anchor="center")
        self.return_tv.pack(fill="both",expand=True,pady=8)
        self.return_tv.bind("<Double-1>",self.edit_return_qty)
        bottom=ttk.Frame(f); bottom.pack(fill="x",pady=8)
        self.return_note=tk.StringVar()
        ttk.Label(bottom,text="ملاحظة").pack(side="right",padx=5)
        ttk.Entry(bottom,textvariable=self.return_note,width=35).pack(side="right",padx=5)
        self.return_total_lbl=ttk.Label(bottom,text="قيمة المرتجع: 0.00",font=("Segoe UI",11,"bold"))
        self.return_total_lbl.pack(side="right",padx=15)
        # تنفيذ الإرجاع من لوحة المفاتيح فقط: F9
        action=ttk.Frame(f)
        action.pack(fill="x",pady=(2,8))
        ttk.Label(action, text="⌨  لتنفيذ الإرجاع اضغط F9", font=("Segoe UI", 9, "bold")).pack(anchor="center")
        self._return_sale_id=None

        # ربط أمر الإرجاع بمفتاح F9 من لوحة المفاتيح.
        # يتم التنفيذ فقط عندما يكون تبويب المرتجعات هو التبويب الحالي.
        self.bind("<F9>", self.keyboard_return_command)

    def keyboard_return_command(self, event=None):
        try:
            current=self.nb.select()
            current_text=self.nb.tab(current, "text")
            if "المرتجعات" not in current_text:
                return
        except Exception:
            return
        self.confirm_return()

    def clear_return_view(self):
        self.return_search.set("")
        self.return_info.config(text="أدخل رقم الفاتورة ثم اضغط بحث.")
        self._return_sale_id=None
        for i in self.return_tv.get_children(): self.return_tv.delete(i)
        self.return_total_lbl.config(text="قيمة المرتجع: 0.00")
        self.return_note.set("")

    def find_return_invoice(self):
        no=self.return_search.get().strip()
        if not no:
            messagebox.showwarning("المرتجعات","أدخل رقم الفاتورة أولاً."); return
        con=db()
        # Robust invoice lookup: normalize Arabic/Persian digits, spaces and punctuation.
        trans=str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
        raw=str(no).translate(trans).strip()
        def norm(v):
            v=str(v or '').translate(trans).lower()
            return ''.join(ch for ch in v if ch.isalnum())
        target=norm(raw)
        sale=None
        rows=con.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
        for r in rows:
            if norm(r['sale_no']) == target:
                sale=r; break
        if sale is None and target:
            matches=[r for r in rows if target in norm(r['sale_no']) or norm(r['sale_no']) in target]
            if len(matches)==1:
                sale=matches[0]
            elif len(matches)>1:
                # Prefer the newest unique candidate.
                sale=matches[0]
        if not sale:
            con.close(); self._return_sale_id=None
            self.return_info.config(text=f"لم يتم العثور على الفاتورة: {no}. تأكد أنك تستخدم رقمًا من تبويب سجل المبيعات.")
            for i in self.return_tv.get_children(): self.return_tv.delete(i)
            self.return_total_lbl.config(text="قيمة المرتجع: 0.00")
            return
        items=con.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",(sale["id"],)).fetchall()
        returned=con.execute("SELECT sale_item_id,COALESCE(SUM(qty),0) q FROM return_items WHERE sale_item_id IN (SELECT id FROM sale_items WHERE sale_id=?) GROUP BY sale_item_id",(sale["id"],)).fetchall()
        retmap={r["sale_item_id"]:r["q"] for r in returned}
        con.close()
        self._return_sale_id=sale["id"]
        self.return_info.config(text=f"الفاتورة {sale['sale_no']} — التاريخ: {sale['sale_time']} — الإجمالي: {money(sale['total'])}")
        for i in self.return_tv.get_children(): self.return_tv.delete(i)
        for x in items:
            ret=int(retmap.get(x["id"],0)); avail=max(0,int(x["qty"])-ret)
            self.return_tv.insert("","end",iid=str(x["id"]),values=(x["id"],x["barcode"],x["name"],x["color"] or "",x["size"] or "",x["qty"],ret,avail,money(x["price"]),0))
        self.update_return_total()

    def edit_return_qty(self,event=None):
        sel=self.return_tv.selection()
        if not sel: return
        item=sel[0]; vals=list(self.return_tv.item(item,"values")); available=int(vals[7])
        x=tk.simpledialog.askinteger("كمية الإرجاع",f"كمية الإرجاع (المتاح {available}):",initialvalue=int(vals[9]),minvalue=0,maxvalue=available)
        if x is not None:
            vals[9]=x; self.return_tv.item(item,values=vals); self.update_return_total()

    def update_return_total(self):
        total=0
        for item in self.return_tv.get_children():
            v=self.return_tv.item(item,"values")
            total += int(v[9] or 0)*float(v[8] or 0)
        self.return_total_lbl.config(text=f"قيمة المرتجع: {money(total)}")

    def confirm_return(self):
        if not self._return_sale_id:
            messagebox.showwarning("المرتجعات","ابحث عن فاتورة أولاً."); return
        selected=[]; total=0
        con=db(); sale=con.execute("SELECT * FROM sales WHERE id=?",(self._return_sale_id,)).fetchone()
        if not sale:
            con.close(); messagebox.showerror("خطأ","الفاتورة غير موجودة."); return
        for iid in self.return_tv.get_children():
            v=self.return_tv.item(iid,"values"); q=int(v[9] or 0)
            if q>0:
                available=int(v[7]);
                if q>available:
                    con.close(); messagebox.showwarning("المرتجعات",f"كمية الإرجاع للمنتج {v[2]} أكبر من المتاح."); return
                selected.append((int(v[0]),v,q,float(v[8])))
                total += q*float(v[8])
        if not selected:
            con.close(); messagebox.showwarning("المرتجعات","حدد كمية الإرجاع أولاً. انقر مرتين على سطر المنتج لتحديد الكمية."); return
        if not messagebox.askyesno("تأكيد الإرجاع",f"سيتم إرجاع {money(total)} وإعادة القطع للمخزون. متابعة؟"):
            con.close(); return
        try:
            now=datetime.now().isoformat(timespec="seconds")
            cur=con.cursor()
            cur.execute("INSERT INTO returns(sale_id,sale_no,return_time,total,note) VALUES(?,?,?,?,?)",
                        (sale["id"],sale["sale_no"],now,total,self.return_note.get().strip()))
            rid=cur.lastrowid
            for item_id,v,q,price in selected:
                si=cur.execute("SELECT * FROM sale_items WHERE id=?",(item_id,)).fetchone()
                if not si: raise ValueError("بند الفاتورة غير موجود")
                cur.execute("INSERT INTO return_items(return_id,sale_item_id,barcode,name,color,size,qty,price,cost) VALUES(?,?,?,?,?,?,?,?,?)",
                            (rid,item_id,si["barcode"],si["name"],si["color"],si["size"],q,si["price"],si["cost"]))
                prod=cur.execute("SELECT id FROM products WHERE barcode=?",(si["barcode"],)).fetchone()
                if prod:
                    cur.execute("UPDATE products SET qty=qty+? WHERE barcode=?",(q,si["barcode"]))
                else:
                    cur.execute("INSERT INTO products(barcode,name,color,size,buy,sell,qty) VALUES(?,?,?,?,?,?,?)",
                                (si["barcode"],si["name"],si["color"],si["size"],si["cost"],si["price"],q))
                cur.execute("INSERT INTO stock_moves(move_time,barcode,move_type,qty,note,ref) VALUES(?,?,?,?,?,?)",
                            (now,si["barcode"],"مرتجع",q,"إرجاع فاتورة",sale["sale_no"]))
            con.commit(); con.close()
        except Exception as e:
            con.rollback(); con.close(); messagebox.showerror("تعذر الإرجاع",str(e)); return
        messagebox.showinfo("تم الإرجاع",f"تم تسجيل المرتجع بقيمة {money(total)} وإعادة الكمية للمخزون.")
        self.find_return_invoice(); self.refresh_inventory(); self.refresh_stocktake(); self.refresh_reports()

    # ---------- PURCHASES / SUPPLIERS / CUSTOMERS ----------
    def purchases_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="🛍️ المشتريات")
        self.section_header(f, "المشتريات")
        form=ttk.LabelFrame(f,text="إضافة شراء للمخزون",padding=10); form.pack(fill="x",pady=5)
        self.pv={}; fields=[("barcode","الباركود"),("name","اسم المنتج"),("color","اللون"),("size","القياس"),("qty","الكمية"),("cost","سعر الشراء")]
        for i,(k,l) in enumerate(fields):
            ttk.Label(form,text=l).grid(row=i//3,column=(i%3)*2+1,padx=5,pady=5,sticky="e")
            self.pv[k]=tk.StringVar(); ttk.Entry(form,textvariable=self.pv[k],width=24).grid(row=i//3,column=(i%3)*2,padx=5,pady=5)
        ttk.Label(form,text="المورد").grid(row=2,column=5,padx=5,pady=5,sticky="e"); self.pv["supplier"]=tk.StringVar(); ttk.Entry(form,textvariable=self.pv["supplier"],width=24).grid(row=2,column=4,padx=5,pady=5)
        ttk.Button(form,text="✓ إضافة للمخزون",command=self.add_purchase).grid(row=3,column=0,columnspan=6,pady=8,sticky="ew")
        self.purchase_tv=ttk.Treeview(f,columns=("no","date","supplier","total"),show="headings")
        for c,h in [("no","رقم الشراء"),("date","التاريخ"),("supplier","المورد"),("total","الإجمالي")]: self.purchase_tv.heading(c,text=h); self.purchase_tv.column(c,width=200,anchor="center")
        self.purchase_tv.pack(fill="both",expand=True,pady=8); self.refresh_purchases()
    def add_purchase(self):
        try:
            code=self.pv["barcode"].get().strip(); name=self.pv["name"].get().strip(); qty=int(self.pv["qty"].get()); cost=float(self.pv["cost"].get())
            if not code or not name or qty<=0: raise ValueError()
            con=db(); now=datetime.now().isoformat(timespec="seconds"); no="PUR-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]; total=qty*cost; cur=con.cursor()
            cur.execute("INSERT INTO purchases(purchase_no,purchase_time,supplier,total) VALUES(?,?,?,?)",(no,now,self.pv["supplier"].get().strip(),total)); pid=cur.lastrowid
            old=cur.execute("SELECT id FROM products WHERE barcode=?",(code,)).fetchone()
            if old: cur.execute("UPDATE products SET qty=qty+?,name=?,color=?,size=?,buy=? WHERE barcode=?",(qty,name,self.pv["color"].get(),self.pv["size"].get(),cost,code))
            else: cur.execute("INSERT INTO products(barcode,name,color,size,buy,sell,qty) VALUES(?,?,?,?,?,?,?)",(code,name,self.pv["color"].get(),self.pv["size"].get(),cost,cost,qty))
            cur.execute("INSERT INTO purchase_items(purchase_id,barcode,name,color,size,qty,cost) VALUES(?,?,?,?,?,?,?)",(pid,code,name,self.pv["color"].get(),self.pv["size"].get(),qty,cost))
            cur.execute("INSERT INTO stock_moves(move_time,barcode,move_type,qty,note,ref) VALUES(?,?,?,?,?,?)",(now,code,"شراء",qty,"فاتورة شراء",no)); con.commit(); con.close()
            for v in self.pv.values(): v.set("")
            self.refresh_inventory(); self.refresh_stocktake(); self.refresh_purchases(); messagebox.showinfo("تم",f"تم تسجيل الشراء {no}")
        except Exception as e: messagebox.showerror("خطأ",f"تأكد من الباركود والكمية والسعر.\n{e}")
    def refresh_purchases(self):
        if not hasattr(self,"purchase_tv"): return
        for i in self.purchase_tv.get_children(): self.purchase_tv.delete(i)
        con=db(); rows=con.execute("SELECT * FROM purchases ORDER BY id DESC LIMIT 300").fetchall(); con.close()
        for r in rows: self.purchase_tv.insert("","end",values=(r["purchase_no"],r["purchase_time"],r["supplier"] or "",money(r["total"])))
    def suppliers_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="🚚 الموردون")
        self.section_header(f, "الموردون")
        form=ttk.Frame(f); form.pack(fill="x",pady=10); self.sv={}
        for i,(k,l) in enumerate([("name","اسم المورد"),("phone","الهاتف"),("note","ملاحظات")]): ttk.Label(form,text=l).grid(row=0,column=i*2+1,padx=5); self.sv[k]=tk.StringVar(); ttk.Entry(form,textvariable=self.sv[k],width=25).grid(row=0,column=i*2,padx=5)
        ttk.Button(form,text="حفظ المورد",command=self.save_supplier).grid(row=1,column=0,columnspan=6,pady=8,sticky="ew")
        self.sup_tv=ttk.Treeview(f,columns=("name","phone","note"),show="headings");
        for c,h in [("name","المورد"),("phone","الهاتف"),("note","ملاحظات")]: self.sup_tv.heading(c,text=h); self.sup_tv.column(c,width=250,anchor="center")
        self.sup_tv.pack(fill="both",expand=True); self.refresh_suppliers()
    def save_supplier(self):
        n=self.sv["name"].get().strip()
        if not n: return
        con=db(); con.execute("INSERT OR REPLACE INTO suppliers(name,phone,note) VALUES(?,?,?)",(n,self.sv["phone"].get(),self.sv["note"].get())); con.commit(); con.close(); self.refresh_suppliers()
    def refresh_suppliers(self):
        if not hasattr(self,"sup_tv"): return
        for i in self.sup_tv.get_children(): self.sup_tv.delete(i)
        con=db(); rs=con.execute("SELECT * FROM suppliers ORDER BY name").fetchall(); con.close()
        for r in rs: self.sup_tv.insert("","end",values=(r["name"],r["phone"] or "",r["note"] or ""))
    def customers_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="👤 الزبائن")
        self.section_header(f, "الزبائن")
        form=ttk.Frame(f); form.pack(fill="x",pady=10); self.cv={}
        for i,(k,l) in enumerate([("name","اسم الزبون"),("phone","الهاتف"),("note","ملاحظات")]): ttk.Label(form,text=l).grid(row=0,column=i*2+1,padx=5); self.cv[k]=tk.StringVar(); ttk.Entry(form,textvariable=self.cv[k],width=25).grid(row=0,column=i*2,padx=5)
        ttk.Button(form,text="حفظ الزبون",command=self.save_customer).grid(row=1,column=0,columnspan=6,pady=8,sticky="ew")
        self.cust_tv=ttk.Treeview(f,columns=("name","phone","note"),show="headings");
        for c,h in [("name","الزبون"),("phone","الهاتف"),("note","ملاحظات")]: self.cust_tv.heading(c,text=h); self.cust_tv.column(c,width=250,anchor="center")
        self.cust_tv.pack(fill="both",expand=True); self.refresh_customers()
    def save_customer(self):
        n=self.cv["name"].get().strip(); ph=self.cv["phone"].get().strip()
        if not n: return
        con=db()
        if ph: con.execute("INSERT OR REPLACE INTO customers(name,phone,note) VALUES(?,?,?)",(n,ph,self.cv["note"].get()))
        else: con.execute("INSERT INTO customers(name,phone,note) VALUES(?,?,?)",(n,None,self.cv["note"].get()))
        con.commit(); con.close(); self.refresh_customers()
    def refresh_customers(self):
        if not hasattr(self,"cust_tv"): return
        for i in self.cust_tv.get_children(): self.cust_tv.delete(i)
        con=db(); rs=con.execute("SELECT * FROM customers ORDER BY id DESC").fetchall(); con.close()
        for r in rs: self.cust_tv.insert("","end",values=(r["name"],r["phone"] or "",r["note"] or ""))

    # ---------- EXPENSES ----------
    def expenses_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="💵 المصاريف")
        self.section_header(f, "المصاريف")
        self.exp_note=tk.StringVar(); self.exp_amt=tk.StringVar()
        form=ttk.Frame(f); form.pack(fill="x",pady=25)
        ttk.Label(form,text="البيان").grid(row=0,column=1,padx=8,pady=8)
        ttk.Entry(form,textvariable=self.exp_note,width=45).grid(row=0,column=0)
        ttk.Label(form,text="المبلغ").grid(row=1,column=1,padx=8,pady=8)
        ttk.Entry(form,textvariable=self.exp_amt,width=45).grid(row=1,column=0)
        ttk.Button(f,text="حفظ المصروف",command=self.save_expense).pack(pady=10)
        ttk.Button(f,text="عرض المصاريف",command=self.show_expenses).pack()

    def save_expense(self):
        try:
            a=float(self.exp_amt.get()); n=self.exp_note.get().strip() or "مصاريف"
            con=db(); con.execute("INSERT INTO expenses(expense_time,note,amount) VALUES(?,?,?)",
                                  (datetime.now().isoformat(timespec="seconds"),n,a)); con.commit(); con.close()
            self.exp_note.set(""); self.exp_amt.set(""); messagebox.showinfo("تم","تم تسجيل المصروف."); self.refresh_reports()
        except: messagebox.showerror("خطأ","أدخل مبلغاً صحيحاً.")

    def show_expenses(self):
        con=db(); rows=con.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 100").fetchall(); con.close()
        w=tk.Toplevel(self); w.title("المصاريف"); w.geometry("800x450")
        tv=ttk.Treeview(w,columns=("date","note","amount"),show="headings")
        for c,h in [("date","التاريخ"),("note","البيان"),("amount","المبلغ")]:
            tv.heading(c,text=h); tv.column(c,width=250)
        tv.pack(fill="both",expand=True,padx=10,pady=10)
        for r in rows: tv.insert("", "end", values=(r["expense_time"],r["note"],money(r["amount"])))

    # ---------- REPORTS ----------
    def reports_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="📊 لوحة التحكم")
        self.section_header(f, "التقارير والأرباح")
        self.cards=tk.Frame(f,bg="#eeeeee"); self.cards.pack(fill="x",pady=8)
        self.card_vars=[]
        labels=["مبيعات اليوم","الربح الإجمالي","المصاريف","الصافي","الفواتير","قيمة المخزون"]
        for lab in labels:
            box=tk.Frame(self.cards,bg="#f5f1e8",bd=1,relief="solid")
            box.pack(side="right",fill="both",expand=True,padx=5)
            tk.Label(box,text=lab,bg="#f5f1e8",font=("Segoe UI",9,"bold")).pack(pady=(10,2))
            v=tk.StringVar(value="0"); self.card_vars.append(v)
            tk.Label(box,textvariable=v,bg="#f5f1e8",font=("Segoe UI",11,"bold")).pack(pady=(2,12))
        ttk.Button(f,text="تحديث",command=self.refresh_reports).pack(anchor="e",pady=8)
        ttk.Label(f,text="المنتجات الأكثر مبيعاً اليوم",font=("Segoe UI",15,"bold")).pack(anchor="e",pady=8)
        self.top_tv=ttk.Treeview(f,columns=("name","qty","sales"),show="headings",height=8)
        for c,h in [("name","المنتج"),("qty","الكمية"),("sales","المبيعات")]:
            self.top_tv.heading(c,text=h); self.top_tv.column(c,width=250)
        self.top_tv.pack(fill="both",expand=True)
        self.refresh_reports()

    def refresh_reports(self):
        if not hasattr(self,"card_vars"): return
        today=datetime.now().date().isoformat(); con=db()
        s=con.execute("SELECT COALESCE(SUM(total),0)t,COALESCE(SUM(profit),0)p,COUNT(*)n FROM sales WHERE date(sale_time)=?",(today,)).fetchone()
        e=con.execute("SELECT COALESCE(SUM(amount),0)e FROM expenses WHERE date(expense_time)=?",(today,)).fetchone()["e"]
        stock=con.execute("SELECT COALESCE(SUM(qty*buy),0)v FROM products").fetchone()["v"]
        tops=con.execute("""SELECT name,SUM(qty) qty,SUM(qty*price) sales FROM sale_items
                           WHERE sale_id IN (SELECT id FROM sales WHERE date(sale_time)=?)
                           GROUP BY name ORDER BY qty DESC LIMIT 10""",(today,)).fetchall()
        con.close()
        vals=[money(s["t"]),money(s["p"]),money(e),money(s["p"]-e),str(s["n"]),money(stock)]
        for v,x in zip(self.card_vars,vals): v.set(x)
        for i in self.top_tv.get_children(): self.top_tv.delete(i)
        for r in tops: self.top_tv.insert("", "end", values=(r["name"],r["qty"],money(r["sales"])))

    # ---------- SETTINGS ----------
    def settings_tab(self):
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text="⚙️ الإعدادات")
        self.section_header(f, "الإعدادات")
        ttk.Label(f,text="MAQAM POS — المرحلة الثالثة",font=("Segoe UI",13,"bold")).pack(anchor="e",pady=15)
        ttk.Label(f,text="نسخة محلية تعمل بدون إنترنت. البيانات محفوظة في maqam_pos.db بجانب البرنامج.",
                  foreground="#555").pack(anchor="e")
        ttk.Button(f,text="نسخ احتياطي لقاعدة البيانات",command=self.backup).pack(anchor="e",pady=12)
        ttk.Button(f,text="استعادة نسخة احتياطية",command=self.restore_backup).pack(anchor="e",pady=5)
        ttk.Button(f,text="تصدير المخزون CSV",command=self.export_csv).pack(anchor="e",pady=5)
        ttk.Button(f,text="فتح مجلد البرنامج",command=lambda:webbrowser.open(str(Path(__file__).parent))).pack(anchor="e",pady=5)

    def backup(self):
        target=filedialog.asksaveasfilename(title="حفظ النسخة الاحتياطية",defaultextension=".db",
            filetypes=[("Database","*.db")],initialfile=f"maqam_backup_{datetime.now():%Y%m%d_%H%M}.db")
        if target: shutil.copy2(DB,target); messagebox.showinfo("تم","تم حفظ النسخة الاحتياطية.")


    def restore_backup(self):
        src=filedialog.askopenfilename(title="اختر نسخة قاعدة البيانات",filetypes=[("Database","*.db")])
        if not src:return
        if not messagebox.askyesno("تأكيد", "سيتم استبدال قاعدة البيانات الحالية. هل لديك نسخة احتياطية منها؟"): return
        try:
            shutil.copy2(src,DB); messagebox.showinfo("تم", "تمت استعادة النسخة. أغلق البرنامج وافتحه من جديد.")
        except Exception as e: messagebox.showerror("خطأ",str(e))

    def export_csv(self):
        target=filedialog.asksaveasfilename(title="تصدير المخزون",defaultextension=".csv",
            filetypes=[("CSV","*.csv")],initialfile="maqam_inventory.csv")
        if not target:return
        con=db(); rows=con.execute("SELECT barcode,name,color,size,buy,sell,qty FROM products ORDER BY name").fetchall(); con.close()
        with open(target,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["Barcode","Name","Color","Size","Buy","Sell","Qty"])
            for r in rows:w.writerow(list(r))
        messagebox.showinfo("تم","تم تصدير المخزون.")

if __name__=="__main__":
    # needed for the simpledialog used by stocktaking
    import tkinter.simpledialog
    db().close()
    App().mainloop()
