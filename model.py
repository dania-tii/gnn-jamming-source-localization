import torch
from torch_geometric.nn import GATConv, global_mean_pool, AttentionalAggregation
from torch.nn import Linear, ReLU, Module
import torch.nn.functional as F
from utils import set_random_seeds

set_random_seeds()


class GraphAttentionNetwork(torch.nn.Module):
    def __init__(self, dropout_rate, num_heads):
        super(GraphAttentionNetwork, self).__init__()
        self.gat1 = GATConv(6, 32, heads=num_heads)  # Input feature dimension is 6, adjust as per your data
        self.gat2 = GATConv(32 * num_heads, 64, heads=num_heads)
        self.attention_pool = AttentionalAggregation(gate_nn=Linear(64 * num_heads, 1))
        self.regressor = torch.nn.Linear(64 * num_heads, 3)  # Assuming output of GlobalAttention is [64]
        self.dropout = torch.nn.Dropout(dropout_rate)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        x = F.relu(self.gat1(x, edge_index))
        # x = self.dropout(x)
        x = F.relu(self.gat2(x, edge_index))
        # x = self.dropout(x)
        x = self.attention_pool(x, data.batch)  # Apply attention pooling to get a single vector for the graph
        # x = global_mean_pool(x, data.batch)  # Pooling to predict a single output per graph
        x = self.dropout(x)  # apply dropout last layer
        x = self.regressor(x)  # Predict the jammer's coordinates
        return x


class SimpleGraphNetwork(Module):
    def __init__(self):
        super(SimpleGraphNetwork, self).__init__()
        self.fc1 = Linear(6, 16)
        self.fc2 = Linear(16, 32)
        self.fc3 = Linear(32, 3)
        self.relu = ReLU()

    def forward(self, data):
        x, batch = data.x, data.batch
        # Apply a fully connected network to each node independently
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.relu(x)
        # aggregate node features to a graph-level prediction # not befitting for our use case?
        x = global_mean_pool(x, batch)
        x = self.fc3(x)
        return x

