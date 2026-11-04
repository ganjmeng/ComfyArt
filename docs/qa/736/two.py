import re,sys
sys.argv=['x']
src=open('/workspace/qaplat/scan.py').read().split('import os')[0].replace("W='/workspace/qaplat/wt/'","W='/tmp/q736/wt/'")
exec(src)
import os
ALLOW=['双11','双十一','11.11','1111','天猫','淘宝','抖音','京东','618','狂欢','预售','热卖','专享','礼遇季','必买','高速吹风机','吹风机','STAGE']
BL=['REVENT','ARTISAN']
def toks(t): return set(x for x in re.split(r'[\s|]+',t) if len(x)>=2)
for o,g in pairs:
    if not os.path.exists(g): print(o,'NOGOLD');continue
    to,tg=txt(W+o),txt(g)
    common=[w for w in toks(to)&toks(tg) if not any(a in w for a in ALLOW)]
    bl=[b for b in BL if b in to.upper()]
    drop=[w for w in hits(tg) if w not in hits(to)]
    print('FAIL' if (common or bl or drop) else 'PASS',o,'common=',common,'bl=',bl,'dropped=',drop)
    if 'promo-ecommerce/examples' in o or 'taobao-product/examples/07' in o: print('  OURS:',to[:600]); print('  GOLD:',tg[:600])
