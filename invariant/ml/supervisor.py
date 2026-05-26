from typing import Any

import torch
import torch.nn as nn
import torch.optim as optim


class FailurePredictionMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)

class MLPSupervisor:
    """model for failure prediction"""

    def __init__(self, input_dim: int):
        self.model = FailurePredictionMLP(input_dim)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.01)
        self.criterion = nn.BCELoss()

    def predict(self, features: torch.Tensor) -> float:
        self.model.eval()
        with torch.no_grad():
            output = self.model(features)
            return float(output.item())

    def train_step(self, features: torch.Tensor, label: torch.Tensor):
        self.model.train()
        self.optimizer.zero_grad()
        output = self.model(features)
        loss = self.criterion(output, label)
        loss.backward()
        self.optimizer.step()
        return loss.item()

# stub for gnn
class GNNSupervisor:
    def __init__(self):
        pass
    def predict(self, graph_data: Any) -> float:
        return 0.5
