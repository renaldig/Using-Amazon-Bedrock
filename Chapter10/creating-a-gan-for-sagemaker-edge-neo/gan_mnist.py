import argparse
import os
import torch
from torchvision import datasets, transforms
from torch import nn, optim
from torch.utils.data import DataLoader

class Generator(nn.Module):
    def __init__(self, latent_dim=100, img_shape=(1, 28, 28)):
        super(Generator, self).__init__()
        self.img_shape = img_shape

        def block(input_dim, output_dim, normalize=True):
            layers = [nn.Linear(input_dim, output_dim)]
            if normalize:
                layers.append(nn.BatchNorm1d(output_dim, 0.8))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
            return layers

        self.model = nn.Sequential(
            *block(latent_dim, 128, normalize=False),
            *block(128, 256),
            *block(256, 512),
            *block(512, 1024),
            nn.Linear(1024, int(torch.prod(torch.tensor(img_shape)))),
            nn.Tanh()
        )

    def forward(self, z):
        img = self.model(z)
        img = img.view(img.size(0), *self.img_shape)
        return img

class Discriminator(nn.Module):
    def __init__(self, img_shape=(1, 28, 28)):
        super(Discriminator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(int(torch.prod(torch.tensor(img_shape))), 512),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(256, 1),
            nn.Sigmoid(),
        )

    def forward(self, img):
        img_flat = img.view(img.size(0), -1)
        validity = self.model(img_flat)
        return validity

def train(args):
    # Configure data loader
    os.makedirs('/tmp/data', exist_ok=True)
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5])
    ])
    dataset = datasets.MNIST('/tmp/data', train=True, download=True, transform=transform)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    # Initialize models
    generator = Generator()
    discriminator = Discriminator()

    # Loss function
    adversarial_loss = nn.BCELoss()

    # Optimizers
    optimizer_G = optim.Adam(generator.parameters(), lr=args.lr)
    optimizer_D = optim.Adam(discriminator.parameters(), lr=args.lr)

    Tensor = torch.FloatTensor

    for epoch in range(args.n_epochs):
        for i, (imgs, _) in enumerate(dataloader):
            # Adversarial ground truths
            valid = torch.ones(imgs.size(0), 1).type(Tensor)
            fake = torch.zeros(imgs.size(0), 1).type(Tensor)

            # Configure input
            real_imgs = imgs.type(Tensor)

            # Train Generator
            optimizer_G.zero_grad()
            z = torch.randn(imgs.size(0), args.latent_dim).type(Tensor)
            gen_imgs = generator(z)
            g_loss = adversarial_loss(discriminator(gen_imgs), valid)
            g_loss.backward()
            optimizer_G.step()

            # Train Discriminator
            optimizer_D.zero_grad()
            real_loss = adversarial_loss(discriminator(real_imgs), valid)
            fake_loss = adversarial_loss(discriminator(gen_imgs.detach()), fake)
            d_loss = (real_loss + fake_loss) / 2
            d_loss.backward()
            optimizer_D.step()

        print(f"[Epoch {epoch+1}/{args.n_epochs}] [D loss: {d_loss.item()}] [G loss: {g_loss.item()}]")

    # Save the generator model
    os.makedirs(args.model_dir, exist_ok=True)
    torch.save(generator.state_dict(), os.path.join(args.model_dir, 'gan_generator.pth'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Training parameters
    parser.add_argument('--n_epochs', type=int, default=5)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=0.0002)
    parser.add_argument('--latent_dim', type=int, default=100)

    # SageMaker parameters
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))

    args = parser.parse_args()

    train(args)