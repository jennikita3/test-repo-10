"""Dibuja los iconos de color del menú de la botella (estilo de los iconos del juego).

Uso: python3 herramientas/dibujar_iconos_botella.py
Guarda los PNG de 128x128 en botella/fuentes/iconos; construir_botella.py los pasa a DST.
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np, math
S=512
SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'botella', 'fuentes', 'iconos')

def mascara(dibujar):
    m=Image.new('L',(S,S),0); dibujar(ImageDraw.Draw(m)); return m

def degradado(mask, c_arriba, c_abajo, luz=(0.35,0.3), fuerza=0.35):
    """Relleno con degradado vertical + un poco de luz radial (efecto volumen)."""
    a=np.array(mask,float)/255
    ys,xs=np.nonzero(a>0.5)
    if len(ys)==0: return Image.new('RGBA',(S,S))
    y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max()
    Y,X=np.mgrid[0:S,0:S]
    t=np.clip((Y-y0)/max(1,y1-y0),0,1)[...,None]
    col=np.array(c_arriba,float)*(1-t)+np.array(c_abajo,float)*t
    cx=x0+(x1-x0)*luz[0]; cy=y0+(y1-y0)*luz[1]; r=max(x1-x0,y1-y0)
    d=np.sqrt((X-cx)**2+(Y-cy)**2)/r
    brillo=np.clip(1-d,0,1)[...,None]*fuerza
    col=col+(255-col)*brillo
    out=np.dstack([np.clip(col,0,255),a*255]).astype(np.uint8)
    return Image.fromarray(out,'RGBA')

def contorno(mask, grosor, color):
    borde=mask.filter(ImageFilter.MaxFilter(grosor*2+1)).filter(ImageFilter.GaussianBlur(1.5))
    im=Image.new('RGBA',(S,S),color); im.putalpha(borde); return im

def reflejo(mask, caja, opacidad=170):
    """Mancha blanca de brillo recortada a la forma."""
    h=Image.new('L',(S,S),0); ImageDraw.Draw(h).ellipse(caja,fill=opacidad)
    h=h.filter(ImageFilter.GaussianBlur(10)); h=ImageChops.multiply(h,mask)
    im=Image.new('RGBA',(S,S),(255,255,255,0)); im.putalpha(h); return im

def capa(mask, arriba, abajo, borde, brillo_caja=None, luz=(0.35,0.3)):
    lienzo=Image.new('RGBA',(S,S),(0,0,0,0))
    lienzo.alpha_composite(contorno(mask,7,borde))
    lienzo.alpha_composite(degradado(mask,arriba,abajo,luz))
    if brillo_caja: lienzo.alpha_composite(reflejo(mask,brillo_caja))
    return lienzo

def rotar(dibujar_horizontal, ang, cx, cy, tam):
    """Dibuja una forma horizontal en una capa aparte, la gira y la coloca."""
    w,h=tam; m=Image.new('L',(w,h),0); dibujar_horizontal(ImageDraw.Draw(m),w,h)
    r=m.rotate(ang,resample=Image.BICUBIC,expand=True)
    out=Image.new('L',(S,S),0); out.paste(r,(int(cx-r.width/2),int(cy-r.height/2))); return out

def botella(ang, cx, cy, escala=1.0):
    L,W=int(330*escala),int(118*escala)
    def cuerpo(d,w,h):
        d.rounded_rectangle([0,0,int(w*0.6),h-1],radius=int(h*0.3),fill=255)
        d.polygon([(int(w*0.58),0),(int(w*0.74),int(h*0.32)),(int(w*0.74),int(h*0.68)),(int(w*0.58),h-1)],fill=255)
        d.rectangle([int(w*0.72),int(h*0.32),int(w*0.93),int(h*0.68)],fill=255)
    def etiqueta(d,w,h):
        d.rounded_rectangle([int(w*0.14),int(h*0.2),int(w*0.44),int(h*0.8)],radius=10,fill=255)
    def corcho(d,w,h):
        d.rounded_rectangle([int(w*0.9),int(h*0.28),w-1,int(h*0.72)],radius=8,fill=255)
    return [rotar(f,ang,cx,cy,(L,W)) for f in (cuerpo,etiqueta,corcho)]

def pintar_botella(lienzo, masks):
    cuerpo,etiqueta,corcho=masks
    todo=ImageChops.lighter(cuerpo,corcho)
    lienzo.alpha_composite(contorno(todo,8,(18,40,24,255)))
    lienzo.alpha_composite(degradado(cuerpo,(120,215,110),(22,110,50),luz=(0.3,0.2),fuerza=0.3))
    lienzo.alpha_composite(degradado(etiqueta,(255,246,220),(225,200,150),fuerza=0.2))
    lienzo.alpha_composite(degradado(corcho,(214,160,100),(140,85,40),fuerza=0.2))
    ys,xs=np.nonzero(np.array(cuerpo)>128)
    cx,cy=xs.mean(),ys.mean()
    lienzo.alpha_composite(reflejo(cuerpo,[cx-120,cy-80,cx+40,cy-10],150))

def corazon(cx,cy,r):
    def f(d):
        d.ellipse([cx-r,cy-r*0.9,cx+r*0.1,cy+r*0.2],fill=255)
        d.ellipse([cx-r*0.1,cy-r*0.9,cx+r,cy+r*0.2],fill=255)
        d.polygon([(cx-r*0.97,cy-r*0.2),(cx+r*0.97,cy-r*0.2),(cx,cy+r*1.05)],fill=255)
    return mascara(f)

def flecha_circular(cx,cy,r,grosor,a0,a1):
    def f(d):
        d.arc([cx-r,cy-r,cx+r,cy+r],a0,a1,fill=255,width=grosor)
        t=math.radians(a1); rm=r-grosor/2
        x,y=cx+rm*math.cos(t),cy+rm*math.sin(t)
        tx,ty=-math.sin(t),math.cos(t); nx,ny=math.cos(t),math.sin(t); h=grosor*1.5
        d.polygon([(x+tx*h*1.3,y+ty*h*1.3),(x+nx*h-tx*h*0.15,y+ny*h-ty*h*0.15),(x-nx*h-tx*h*0.15,y-ny*h-ty*h*0.15)],fill=255)
    return mascara(f)

def sombra(lienzo):
    a=lienzo.split()[3].filter(ImageFilter.GaussianBlur(9))
    s=Image.new('RGBA',(S,S),(0,0,0,0)); s.putalpha(a.point(lambda v:int(v*0.45)))
    out=Image.new('RGBA',(S,S),(0,0,0,0)); out.paste(s,(6,10)); out.alpha_composite(lienzo); return out

def final(lienzo,nombre):
    im=sombra(lienzo).resize((128,128),Image.LANCZOS); im.save(nombre); return im

# --- Jugar a la botella: botella verde + corazón rosa
L=Image.new('RGBA',(S,S),(0,0,0,0))
pintar_botella(L, botella(28,236,300,1.05))
c=corazon(360,150,92)
L.alpha_composite(capa(c,(255,140,190),(215,30,110),(90,10,45,255),[285,85,365,145]))
jugar=final(L,os.path.join(SALIDA,'Jennikita_Botella_Icono_Jugar.png'))

# --- Girar la botella: botella + flecha circular naranja
L=Image.new('RGBA',(S,S),(0,0,0,0))
f1=flecha_circular(256,256,205,40,195,300); f2=flecha_circular(256,256,205,40,15,120)
for f in (f1,f2): L.alpha_composite(capa(f,(255,225,90),(240,120,0),(110,50,0,255),None,luz=(0.3,0.1)))
pintar_botella(L, botella(28,256,262,1.0))
girar=final(L,os.path.join(SALIDA,'Jennikita_Botella_Icono_Girar.png'))

