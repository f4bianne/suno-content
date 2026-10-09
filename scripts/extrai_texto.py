# Extrai o texto dos PDFs e HTMLs de dados/corpus/ para dados/corpus/texto/ (fora do git).
# Uso: python scripts/extrai_texto.py
import sys,os,glob,re,html
from multiprocessing import Pool
sys.stdout.reconfigure(encoding='utf-8')
def pdf(p):
    out='dados/corpus/texto/'+os.path.relpath(p,'dados/corpus').replace(os.sep,'__').replace('/','__')[:-4]+'.txt'
    if os.path.exists(out): return p,'skip'
    try:
        import pypdf
        r=pypdf.PdfReader(p)
        t='\n'.join((pg.extract_text() or '') for pg in r.pages)
        open(out,'w',encoding='utf-8').write(t); return p,len(t)
    except Exception as e: return p,'ERR '+str(e)[:40]
def htm(p):
    out='dados/corpus/texto/'+os.path.relpath(p,'dados/corpus').replace(os.sep,'__').replace('/','__')[:-5]+'.txt'
    s=open(p,encoding='utf-8',errors='ignore').read()
    s=re.sub(r'(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>','',s)
    s=re.sub(r'(?s)<[^>]+>','\n',s); s=html.unescape(s)
    s=re.sub(r'\n\s*\n+','\n',s)
    open(out,'w',encoding='utf-8').write(s); return p,len(s)
if __name__=='__main__':
    pdfs=[p for p in glob.glob('dados/corpus/**/*.pdf',recursive=True) if 'glossarios' not in p]
    with Pool(6) as pool: res=pool.map(pdf,pdfs,chunksize=2)
    for p in glob.glob('dados/corpus/**/*.html',recursive=True): res.append(htm(p))
    bad=[r for r in res if isinstance(r[1],str) and r[1]!='skip']
    print(len(res),'arquivos; erros:',bad)
