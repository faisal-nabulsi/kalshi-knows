"""Contrastive pretraining (SimCLR) of a small 1D-CNN encoder on Kalshi price-path windows, then
use its embeddings as extra features for the play classifier.

Self-supervised stage: 53k unlabeled 64-second windows (price change + trade counts on a 2 s grid) from all
2026 real price paths; two random augmentations of the same window should embed close together (NT-Xent loss).
Supervised stage (done back on the Mac in finetune_real.py): the encoder's embedding of each detector fire
(PCA to 8 dims) is appended to the stacked XGBoost features and compared under the same GroupKFold-by-game CV.

Run on the GPU box: ./venv/bin/python -u contrastive.py   (logs to W&B offline)
"""
import json, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

try:
    import wandb
except ImportError:
    wandb = None

torch.manual_seed(7); np.random.seed(7)
dev = "cuda" if torch.cuda.is_available() else "cpu"
U = torch.tensor(np.load("crops_unlabeled.npy"))     # (N, 2, 32)
L = torch.tensor(np.load("crops_labeled.npy"))       # (M, 2, 32)
scale = U[:, 0].abs().std().item() + 1e-6           # normalize the price channel


class Encoder(nn.Module):
    def __init__(self, d=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(2, 32, 5, padding=2), nn.GELU(), nn.BatchNorm1d(32),
            nn.Conv1d(32, 64, 5, padding=2, stride=2), nn.GELU(), nn.BatchNorm1d(64),
            nn.Conv1d(64, 64, 3, padding=1), nn.GELU(), nn.AdaptiveAvgPool1d(1))
        self.fc = nn.Linear(64, d)

    def forward(self, x):
        x = torch.stack([x[:, 0] / scale, x[:, 1]], 1)
        return self.fc(self.net(x).squeeze(-1))


def augment(x):
    x = x.clone()
    x[:, 0] = x[:, 0] * torch.empty(len(x), 1, device=x.device).uniform_(0.8, 1.2)       # amplitude
    x[:, 0] = x[:, 0] + 0.004 * torch.randn_like(x[:, 0])                               # quote noise
    shift = int(torch.randint(-2, 3, (1,)))                                              # +-4 s time shift
    x = torch.roll(x, shifts=shift, dims=2)
    drop = (torch.rand(len(x), 1, device=x.device) < 0.3).float()                        # sometimes hide trade counts
    x[:, 1] = x[:, 1] * (1 - drop)
    return x


def nt_xent(z1, z2, tau=0.2):
    z = F.normalize(torch.cat([z1, z2]), dim=1)
    sim = z @ z.t() / tau
    n = len(z1)
    sim.fill_diagonal_(-1e9)
    target = torch.cat([torch.arange(n, 2 * n), torch.arange(0, n)]).to(z.device)
    return F.cross_entropy(sim, target)


enc = Encoder().to(dev)
head = nn.Sequential(nn.Linear(64, 64), nn.GELU(), nn.Linear(64, 32)).to(dev)
opt = torch.optim.AdamW(list(enc.parameters()) + list(head.parameters()), lr=2e-3, weight_decay=1e-4)
EPOCHS, BS = 40, 1024
run = wandb.init(project="kalshi-knows", mode="offline", group="contrastive", job_type="pretrain",
                 name="simclr-1dcnn-price-paths",
                 config={"unlabeled_windows": len(U), "epochs": EPOCHS, "batch": BS, "tau": 0.2, "embed": 64}) if wandb else None
Ud = U.to(dev)
t0 = time.time()
for ep in range(EPOCHS):
    perm = torch.randperm(len(Ud), device=dev); tot = 0; nb = 0
    enc.train(); head.train()
    for i in range(0, len(Ud) - BS + 1, BS):
        x = Ud[perm[i:i + BS]]
        loss = nt_xent(head(enc(augment(x))), head(enc(augment(x))))
        opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item(); nb += 1
    print(f"epoch {ep} nt_xent {tot / nb:.4f}")
    if run:
        run.log({"epoch": ep, "pretrain/nt_xent": tot / nb})

enc.eval()
with torch.no_grad():
    E = enc(L.to(dev)).cpu().numpy()
    Eu = enc(Ud[:20000]).cpu().numpy()
# PCA to 8 dims fit on unlabeled embeddings (no label information used)
mu = Eu.mean(0); _, _, Vt = np.linalg.svd(Eu - mu, full_matrices=False)
E8 = (E - mu) @ Vt[:8].T
np.save("contrastive_emb.npy", E8.astype(np.float32))
torch.save({"enc": enc.state_dict(), "scale": scale, "pca_mu": mu, "pca_V": Vt[:8]}, "contrastive_encoder.pt")
json.dump({"seconds": time.time() - t0, "final_nt_xent": tot / nb, "labeled": len(L)}, open("contrastive_meta.json", "w"))
if run:
    run.summary.update({"final_nt_xent": tot / nb}); run.finish()
print("done", round(time.time() - t0), "s")
