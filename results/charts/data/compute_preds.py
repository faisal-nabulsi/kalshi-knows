import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/train')
import eval_real as ER, finetune_real as FR
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
C=ER.CLASSES; K=len(C)
out={}
# ---- real 417
X,y,g,a=ER.load_real()
bst=xgb.Booster(); bst.load_model(str(ER.OUT/'playinfer_xgb.json'))
Px=bst.predict(xgb.DMatrix(X,feature_names=ER.FEATURES),iteration_range=(0,ER.spec['best_iteration']+1))
Pc=ER.cv_logreg(np.log(np.clip(Px,1e-6,1)),y,g)
Pr=ER.rule_of_thumb(X)
out['r417']={'y':y.tolist(),'pred':Pc.argmax(1).tolist(),'conf':Pc.max(1).tolist(),'rule_pred':Pr.argmax(1).tolist(),
  'acc':float((Pc.argmax(1)==y).mean()),'rule_acc':float((Pr.argmax(1)==y).mean()), 'n':len(y),'games':len(set(g))}
# ---- fires
df=pd.read_parquet(FR.ROOT/'pipeline/out/real_windows.parquet')
rows=FR.build_rows(df,FR.FIRE_TRAIN); rows=rows[rows.category.isin(C)].reset_index(drop=True)
yf=rows.category.map({c:i for i,c in enumerate(C)}).to_numpy(); gf=rows.game_id.to_numpy()
Xs,Z,b=FR.sim_logprobs(rows)
F=pd.concat([pd.DataFrame(Z,columns=[f'sim_{c}' for c in C]),rows[FR.STATE+FR.MICRO].reset_index(drop=True)],axis=1).astype(float)
xp={"objective":"multi:softprob","num_class":K,"max_depth":3,"learning_rate":0.05,"subsample":0.8,"colsample_bytree":0.8,"min_child_weight":3,"lambda":3.0,"tree_method":"hist"}
def fp(tr,te):
    bb=xgb.train(xp,xgb.DMatrix(F.to_numpy()[tr],yf[tr]),300); return bb.predict(xgb.DMatrix(F.to_numpy()[te]))
Ps=FR.cv(yf,gf,fp)
Xr=pd.DataFrame({'delta_pos':np.where(rows.posteam_is_home==1,rows.delta_home,-rows.delta_home)}); Xr['abs_delta']=rows.delta_home.abs()
Prf=np.full((len(rows),K),0.02)
for i,(o,bg) in enumerate(zip(Xr.delta_pos.to_numpy()>0,Xr.abs_delta.to_numpy()>=0.10)):
    Prf[i,C.index('TD' if (o and bg) else 'BIG_PLAY' if o else 'TURNOVER')]=0.9
live=(rows.delta_home.abs()>=0.08).to_numpy()
maj=np.full(len(rows),C.index('OTHER'))
out['fires']={'y':yf.tolist(),'pred':Ps.argmax(1).tolist(),'conf':Ps.max(1).tolist(),'rule_pred':Prf.argmax(1).tolist(),'live':live.tolist(),
  'acc':float((Ps.argmax(1)==yf).mean()),'rule_acc':float((Prf.argmax(1)==yf).mean()),'maj_acc':float((maj==yf).mean()),
  'rule_acc_live':float((Prf.argmax(1)==yf)[live].mean()),'maj_acc_live':float((maj==yf)[live].mean()),'acc_live':float((Ps.argmax(1)==yf)[live].mean()),
  'n':len(yf),'n_live':int(live.sum()),'games':len(set(gf)),'classes':C}
json.dump(out,open('/tmp/kk/preds.json','w'))
print({k:{kk:vv for kk,vv in v.items() if not isinstance(vv,list)} for k,v in out.items()})
