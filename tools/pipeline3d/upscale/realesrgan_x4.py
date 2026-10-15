#!/usr/bin/env python3
import numpy as np, cv2, torch, torch.nn as nn, torch.nn.functional as F

class ResidualDenseBlock(nn.Module):
    def __init__(self, nf=64, gc=32):
        super().__init__()
        self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
        self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
        self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
        self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
        self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, True)
    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        return self.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x

class RRDB(nn.Module):
    def __init__(self, nf):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(nf)
        self.rdb2 = ResidualDenseBlock(nf)
        self.rdb3 = ResidualDenseBlock(nf)
    def forward(self, x):
        out = self.rdb1(x); out = self.rdb2(out); out = self.rdb3(out)
        return out * 0.2 + x

class RRDBNet(nn.Module):
    def __init__(self, nf=64, nb=23):
        super().__init__()
        self.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(nf) for _ in range(nb)])
        self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, True)
    def forward(self, x):
        feat = self.conv_first(x)
        body_feat = self.body(feat)
        feat = feat + self.conv_body(body_feat)
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode='nearest')))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode='nearest')))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))

sd = torch.load('/tmp/RealESRGAN_x4plus.pth', map_location='cpu', weights_only=True)
sd = sd.get('params_ema', sd)
net = RRDBNet()
net.load_state_dict(sd, strict=True)
net.eval()
print("strict load OK")

for src, dst in [("/Users/user0/godot-hybrid-casual/assets/ref_orange_upright.png", "/tmp/waifu_upright_4x.png"),
                 ("/Users/user0/godot-hybrid-casual/assets/ref_orange_inverted.png", "/tmp/waifu_inverted_4x.png")]:
    img = cv2.imread(src, cv2.IMREAD_COLOR).astype(np.float32) / 255.0
    t = torch.from_numpy(np.transpose(img[:, :, [2, 1, 0]], (2, 0, 1))).unsqueeze(0)
    with torch.no_grad():
        out = net(t).clamp_(0, 1)
    out = out.squeeze(0).permute(1, 2, 0).numpy()[:, :, [2, 1, 0]]
    cv2.imwrite(dst, (out * 255).round().astype(np.uint8))
    print(dst, out.shape)
