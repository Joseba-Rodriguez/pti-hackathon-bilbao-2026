"""Calibra el gemelo con las grabaciones: vaso en la imagen tras soltar frente a la punta FK al soltar -> homografia.

Uso (desde E:\HACKATONLeRobot\lerobot): .venv\Scripts\python.exe ..\herramientas\calibrar_gemelo.py pti_laser_todo pti_laser_H_centro ...
Imprime la homografia; copiarla a herramientas/gemelo_calibracion.json -> camara_a_robot.H."""
import sys, glob, json, numpy as np, pandas as pd, cv2, mujoco
sys.path.insert(0, r"E:\HACKATONLeRobot\lerobot\examples\so101_mujoco")
from so101_assets import menagerie_spec
m = menagerie_spec().compile(); d = mujoco.MjData(m)
J = ["Rotation","Pitch","Elbow","Wrist_Pitch","Wrist_Roll","Jaw"]
ids=[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j) for j in J]
adr=[m.jnt_qposadr[i] for i in ids]; rng=[m.jnt_range[i] for i in ids]
pads=[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, g) for g in ("fixed_jaw_pad_2","moving_jaw_pad_2")]
SIGN=[-1,1,1,1,1]
def tip(q):
    for i in range(5): d.qpos[adr[i]]=np.clip(0.5*(rng[i][0]+rng[i][1])+SIGN[i]*np.radians(q[i]),*rng[i])
    mujoco.mj_kinematics(m,d); return 0.5*(d.geom_xpos[pads[0]]+d.geom_xpos[pads[1]])
def vaso(im):
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); b,gg,r=[im[...,k].astype(int) for k in range(3)]
    dark=(g<45).astype(np.uint8); n,lab,st,cen=cv2.connectedComponentsWithStats(dark)
    k=1+np.argmax(st[1:,4]); board=(lab==k).astype(np.uint8)
    hull=np.zeros_like(board); cnts,_=cv2.findContours(board,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.fillPoly(hull,[cv2.convexHull(max(cnts,key=cv2.contourArea))],1)
    red=(r-np.maximum(gg,b))>30
    holes=((hull==1)&(board==0)&~red).astype(np.uint8)
    holes=cv2.erode(holes,np.ones((3,3),np.uint8)); holes=cv2.morphologyEx(holes,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    n,lab,st,cen=cv2.connectedComponentsWithStats(holes); best=None; ba=0
    for k in range(1,n):
        x,y,w,h,a=st[k]
        if 300<a<2500 and 0.6<w/h<1.6 and a>ba and a/(w*h)>0.55: best=(cen[k][0],cen[k][1]); ba=a
    return best
def circulo(im):
    b,g,r=[im[...,i].astype(int) for i in range(3)]
    mk=((r>170)&(g<90)&(b<90)).astype(np.uint8)
    n,lab,st,cen=cv2.connectedComponentsWithStats(mk)
    best=None
    for k in range(1,n):
        a=st[k,4]; w,h=st[k,2],st[k,3]
        if 200<a<700 and 0.7<w/h<1.4 and 18<=w<=32:
            cx,cy=cen[k]; c=im[int(cy),int(cx)]
            if c.min()>110: best=(cx,cy)
    return best
pares=[]; NREL=[0]
for ds in sys.argv[1:]:
    D=rf"E:\HACKATONLeRobot\hf_cache\lerobot\Josebarv01\{ds}"
    df=pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(D+r"\data\*\*.parquet"))])
    E=pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(D+r"\meta\episodes\*\*.parquet"))]).set_index("episode_index")
    caps={}
    for ep,g in df.groupby("episode_index"):
        s=np.stack(g["observation.state"]); gr=s[:,5]
        held=0; rel=None
        for i in range(len(gr)):
            if 8<gr[i]<27: held+=1
            elif gr[i]>=26 and held>30: rel=i; break
            else: held=0
        NREL[0]+=rel is not None
        if rel is None: continue
        e=E.loc[ep]; f=int(e["videos/observation.images.top/file_index"]); ck=int(e.get("videos/observation.images.top/chunk_index",0))
        key=(ck,f)
        if key not in caps: caps[key]=cv2.VideoCapture(rf"{D}\videos\observation.images.top\chunk-{ck:03d}\file-{f:03d}.mp4")
        cap=caps[key]; t0=float(e["videos/observation.images.top/from_timestamp"])
        last=None
        for fr in (len(gr)-2, len(gr)-10):
            cap.set(cv2.CAP_PROP_POS_MSEC,1000*(t0+fr/30)); ok,im=cap.read()
            if ok:
                c=vaso(im)
                if c: last=c; break
        if last: pares.append((ds,int(ep),last[0],last[1],*tip(s[rel])[:2]))
print(len(pares),"pares", NREL)
P=np.array([p[2:] for p in pares],float)
H,inl=cv2.findHomography(P[:,:2],P[:,2:]*100,cv2.RANSAC,3.0)
pred=cv2.perspectiveTransform(P[:,None,:2],H)[:,0]; err=np.linalg.norm(pred-P[:,2:]*100,axis=1)
print("inliers",int(inl.sum()),"error cm mediana",np.median(err[inl[:,0]==1]).round(2),"p90",np.percentile(err[inl[:,0]==1],90).round(2))
json.dump({"H_px_a_cm":H.tolist(),"pares":len(pares),"inliers":int(inl.sum()),"err_mediana_cm":float(np.median(err[inl[:,0]==1]))},sys.stdout,indent=1)
