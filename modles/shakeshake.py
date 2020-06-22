# -*- coding: utf-8 -*-
"""ShakeShake.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1AN1kMuQckdJGyduv1zSwW8qRTxFQtHxy
"""

# shakeshake net leaning heavily on the original torch implementation https://github.com/xgastaldi/shake-shake/
class ShakeShakeBlock2d(torch.nn.Module):
    def __init__(self, in_channels, out_channels, stride, per_image=True, rand_forward=True, rand_backward=True):
        super().__init__()
        self.same_width = (in_channels==out_channels)
        self.per_image = per_image
        self.rand_forward = rand_forward
        self.rand_backward = rand_backward
        self.stride = stride
        self.net1, self.net2 = [torch.nn.Sequential(
                        torch.nn.ReLU(),
                        torch.nn.Conv2d(in_channels, out_channels, 3, stride=stride, padding=1),
                        torch.nn.BatchNorm2d(out_channels),
                        torch.nn.ReLU(),
                        torch.nn.Conv2d(out_channels, out_channels, 3, padding=1),
                        torch.nn.BatchNorm2d(out_channels)) for i in range(2)]
        if not self.same_width:
            self.skip_conv1 = torch.nn.Conv2d(in_channels, out_channels//2, 1)
            self.skip_conv2 = torch.nn.Conv2d(in_channels, out_channels//2, 1)
            self.skip_bn = torch.nn.BatchNorm2d(out_channels)
    def forward(self, inp):
        if self.same_width:
            skip = inp
        else:
            # double check, this seems to be a fancy way to trow away the top-right and bottom-left of each 2x2 patch (with stride=2)
            x1 = torch.nn.functional.avg_pool2d(inp, 1, stride=self.stride)
            x1 = self.skip_conv1(x1)
            x2 = torch.nn.functional.pad(inp, (1,-1,1,-1))            # this makes the top and leftmost row 0. one could use -1,1
            x2 = torch.nn.functional.avg_pool2d(x2, 1, stride=self.stride)
            x2 = self.skip_conv2(x2)
            skip = torch.cat((x1,x2), dim=1)
            skip = self.skip_bn(skip)
        x1 = self.net1(inp)
        x2 = self.net2(inp)

        if self.training:
            if self.rand_forward:
                if self.per_image:
                    alpha = Variable(inp.data.new(inp.size(0),1,1,1).uniform_())
                else:
                    alpha = Variable(inp.data.new(1,1,1,1).uniform_())
            else:
                alpha = 0.5
            if self.rand_backward:
                if self.per_image:
                    beta = Variable(inp.data.new(inp.size(0),1,1,1).uniform_())
                else:
                    beta = Variable(inp.data.new(1,1,1,1).uniform_())
            else:
                beta = 0.5
            # this is the trick to get beta in the backward (because it does not see the detatched)
            # and alpha in the forward (when it sees the detached with the alpha and the beta cancel)
            x = skip+beta*x1+(1-beta)*x2+((alpha-beta)*x1).detach()+((beta-alpha)*x2).detach()
        else:
            x = skip+0.5*(x1+x2)
        return x

            
class ShakeShakeBlocks2d(torch.nn.Sequential):
    def __init__(self, in_channels, out_channels, depth, stride, per_image=True, rand_forward=True, rand_backward=True):
        super().__init__(*[
            ShakeShakeBlock2d(in_channels if i==0 else out_channels, out_channels, stride if i==0 else 1,
                              per_image, rand_forward, rand_backward) for i in range(depth)])

class ShakeShakeNet(torch.nn.Module):
    def __init__(self, depth=20, basewidth=32, per_image=True, rand_forward=True, rand_backward=True, num_classes=16):
        super().__init__()
        assert (depth - 2) % 6==0, "depth should be n*6+2"
        n = (depth - 2) // 6
        self.inconv = torch.nn.Conv2d(3, 16, 3, padding=1)
        self.bn1 = torch.nn.BatchNorm2d(16)
        self.s1 = ShakeShakeBlocks2d(16, basewidth, n, 1, per_image, rand_forward, rand_backward)
        self.s2 = ShakeShakeBlocks2d(basewidth, 2*basewidth, n, 2, per_image, rand_forward, rand_backward)
        self.s3 = ShakeShakeBlocks2d(2*basewidth, 4*basewidth, n, 2, per_image, rand_forward, rand_backward)
        self.fc = torch.nn.Linear(4*basewidth, num_classes)
    def forward(self, x):
        x = self.inconv(x)
        x = self.bn1(x)
        x = self.s1(x)
        x = self.s2(x)
        x = self.s3(x)
        x = torch.nn.functional.relu(x)
        x = x.view(x.size(0), x.size(1), -1).mean(2)
        x = self.fc(x)
        return x
model = ShakeShakeNet()
model.cuda()