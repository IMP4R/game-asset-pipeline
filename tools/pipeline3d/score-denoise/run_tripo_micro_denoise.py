import sys, types, torch, numpy as np, json
from pathlib import Path

# Compatibility shim: the released 189k-parameter model only needs KNN from PyTorch3D.
def knn_points(x,y,K,return_nn=False):
    d=torch.cdist(x,y)**2
    vals,idx=torch.topk(d,K,dim=-1,largest=False,sorted=True)
    nn=None
    if return_nn:
        B,N,_=x.shape; D=y.shape[-1]
        yy=y[:,None,:,:].expand(B,N,y.shape[1],D)
        nn=torch.gather(yy,2,idx[...,None].expand(B,N,K,D))
    return vals,idx,nn
ops=types.ModuleType('pytorch3d.ops');ops.knn_points=knn_points
loss=types.ModuleType('pytorch3d.loss'); loss.chamfer_distance=lambda *a,**k: None; loss.point_mesh_face_distance=lambda *a,**k: None
pmd=types.ModuleType('pytorch3d.loss.point_mesh_distance'); pmd.point_face_distance=lambda *a,**k: None
structures=types.ModuleType('pytorch3d.structures'); structures.Pointclouds=object; structures.Meshes=object
p3d=types.ModuleType('pytorch3d');p3d.__path__=[];p3d.ops=ops;p3d.loss=loss;p3d.structures=structures
sys.modules.update({'pytorch3d':p3d,'pytorch3d.ops':ops,'pytorch3d.loss':loss,'pytorch3d.loss.point_mesh_distance':pmd,'pytorch3d.structures':structures})
tc=types.ModuleType('torch_cluster'); tc.fps=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('FPS is not used in direct identity-preserving inference'))
sys.modules['torch_cluster']=tc

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from models.denoise import DenoiseNet

inp,out,ckpt_path=sys.argv[1:4]
device='mps' if torch.backends.mps.is_available() else 'cpu'
ckpt=torch.load(ckpt_path,map_location='cpu',weights_only=False)
model=DenoiseNet(ckpt['args']).to(device);model.load_state_dict(ckpt['state_dict']);model.eval()
data=np.load(inp)
outputs={}; report=[]
for key in data.files:
    p=torch.tensor(data[key],dtype=torch.float32,device=device)
    center=(p.max(0).values+p.min(0).values)/2
    q=p-center; scale=torch.linalg.norm(q,dim=1).max(); q=q/scale
    original=q.clone()
    # Direct ordered inference: unlike the paper's patch/FPS wrapper, this preserves vertex identity.
    # Conservative 8-step pass and displacement cap protect generated shape and contact regions.
    with torch.no_grad():
        den,_=model.denoise_langevin_dynamics(q[None],step_size=.055,denoise_knn=4,step_decay=.82,num_steps=8)
        den=den[0]
    delta=den-original
    cap=.0125
    mag=torch.linalg.norm(delta,dim=1,keepdim=True)
    delta=delta*torch.clamp(cap/(mag+1e-9),max=1.0)
    # Blend at 65%; network proposes a residual rather than replacing geometry.
    corrected=(original+.65*delta)*scale+center
    outputs[key]=corrected.cpu().numpy().astype(np.float32)
    mw=(.65*delta*scale).norm(dim=1).cpu().numpy()
    report.append({'component':key,'points':len(p),'mean_shift':float(mw.mean()),'p95_shift':float(np.percentile(mw,95)),'max_shift':float(mw.max())})
    print(report[-1])
np.savez(out,**outputs)
with open(out+'.json','w') as f:json.dump({'device':device,'params':sum(x.numel() for x in model.parameters()),'components':report},f,indent=2)
