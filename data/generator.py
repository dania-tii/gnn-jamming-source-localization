import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import random
from tqdm import tqdm

# Constants
LIGHT_SPEED = 3e8  # Speed of light (m/s), used in path loss calculations
FREQUENCY = 2.4e9  # Operating frequency in Hz (e.g., 2.4 GHz for WiFi)
NOISE_LEVEL = -100  # Ambient noise level at the receiver in dBm [-100, -90]
REFERENCE_SINR = 10  # Typical SINR in dB under normal conditions
NOISE_THRESHOLD = -55  # A jamming attack is deemed successful if the floor noise > NOISE_THRESHOLD
RSSI_THRESHOLD = -80  # Minimum RSSI threshold (represents the point where communication is effectively non-functional)
MESH_NETWORK = True  # Set to True for mesh network, False for AP-client network
JAMMER_OUTSIDE_SAMPLE = True  # Set True to ensure jammer position is generated outside the node positions sampled region
ALL_JAMMED = False  # Set True to ensure every node in network is jammed
ENV = "fspl"  # "shadowed_urban_area" # fspl # Set type of propagation environment
PLOT = False

def dbm_to_linear(dbm):
    """Convert dBm to linear scale (milliwatts)."""
    return 10 ** (dbm / 10)


def linear_to_db(linear):
    """Convert linear scale (milliwatts) to dB."""
    return 10 * np.log10(linear)


def log_distance_path_loss(d, pl0=32, d0=1, n=2.1, sigma=2):
    # Prevent log of zero if distance is zero by replacing it with a very small positive number
    d = np.where(d == 0, np.finfo(float).eps, d)
    # Calculate the path loss
    path_loss = pl0 + 10 * n * np.log10(d / d0)
    # Add shadow fading if sigma is not zero
    if sigma != 0:
        path_loss += np.random.normal(0, sigma, size=d.shape)
    return path_loss


def free_space_path_loss(d):
    """Calculate free space path loss given distance d in meters."""
    # Replace zero distances with a very small positive number
    d = np.where(d == 0, np.finfo(float).eps, d)
    return 20 * np.log10(d) + 20 * np.log10(FREQUENCY) + 20 * np.log10(4 * np.pi / LIGHT_SPEED)  # FSPL formula


def sample_path_jamming(node_pos_i, node_pos_j, jammer_pos, loss_func, n, sigma, num_samples=10):
    # Linearly interpolate points between node_pos_i and node_pos_j
    line_points = np.linspace(node_pos_i, node_pos_j, num=num_samples, endpoint=True)
    max_jamming_power_dbm = -np.inf
    for point in line_points:
        # Calculate distance from this point to the jammer
        dist_to_jammer = np.linalg.norm(point - jammer_pos)
        # Compute jamming power at this point using path loss model
        if loss_func == log_distance_path_loss:
            jamming_power_dbm = P_tx_jammer + G_tx_jammer + G_rx - loss_func(dist_to_jammer, n=n, sigma=sigma)
        else:
            jamming_power_dbm = P_tx_jammer + G_tx_jammer + G_rx - loss_func(dist_to_jammer)
        max_jamming_power_dbm = max(max_jamming_power_dbm, jamming_power_dbm)
    return max_jamming_power_dbm


def calculate_node_bounds(arena_size):
    # Constants
    node_range = 200.0  # average comm. range in meters

    # Calculate number of nodes required for horizontal/vertical coverage
    min_nodes_h = math.ceil(arena_size / node_range)

    # Calculate the diagonal of the arena
    diagonal = arena_size * math.sqrt(2)

    # Calculate number of nodes required for diagonal coverage
    min_nodes_diagonal = math.ceil(diagonal / node_range)

    return min_nodes_h + min_nodes_diagonal


def calculate_maximum_distance(center_x, center_y, angle, size):
    # Determine points where the line intersects the boundaries
    intersections = []
    for bound_x in [0, size]:
        bound_y = center_y + (bound_x - center_x) / np.tan(angle)
        if 0 <= bound_y <= size:
            intersections.append((bound_x, bound_y))
    for bound_y in [0, size]:
        bound_x = center_x + (bound_y - center_y) * np.tan(angle)
        if 0 <= bound_x <= size:
            intersections.append((bound_x, bound_y))

    # Calculate the maximum distance within bounds
    max_distance = 0
    for x, y in intersections:
        distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
        if distance > max_distance:
            max_distance = distance
    return max_distance


def plot_network_with_rssi(node_positions, final_rssi, jammer_position, sinr_db, noise_floor_db, jammed):
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot nodes
    for idx, pos in enumerate(node_positions):
        color = 'red' if jammed[idx] else 'blue'

        # Check if the node is effectively disconnected based on RSSI
        node_info = f"Node {idx}\nRSSI: {final_rssi[idx]:.2f} dB\nSINR: {sinr_db[idx]:.2f} dB\nNoise: {noise_floor_db[idx]:.2f} dB"
        ax.plot(pos[0], pos[1], 'o', color=color)  # Nodes in blue or red depending on jamming status
        ax.text(pos[0], pos[1], node_info, fontsize=9, ha='right')

    # Plot jammer
    ax.plot(jammer_position[0], jammer_position[1], 'r^', markersize=10)  # Jammer in red
    ax.text(jammer_position[0], jammer_position[1], ' Jammer', verticalalignment='bottom', horizontalalignment='right', color='red', fontsize=10)

    ax.set_title('Network Topology with RSSI, SINR, and Noise Floor', fontsize=11)
    ax.set_xlabel('X position (m)', fontsize=14)
    ax.set_ylabel('Y position (m)', fontsize=14)
    plt.grid(True)
    plt.show()


def get_position(n_nodes, size, placement='random'):
    if placement == 'random':
        positions = np.random.rand(n_nodes, 2) * size
    elif placement == 'circle':
        angles = np.linspace(0, 2 * np.pi, n_nodes, endpoint=False)
        x = size / 2 * np.cos(angles) + size / 2
        y = size / 2 * np.sin(angles) + size / 2
        positions = np.column_stack((x, y))
    elif placement == 'triangle':
        positions = np.zeros((n_nodes, 2))
        sides = 3
        # Calculate points per side and determine extra points
        points_per_side, additional_points = divmod(n_nodes, sides)
        # Generate a random angle for rotation (in radians)
        random_rotation = np.random.uniform(0, 2 * np.pi)
        index = 0  # Initialize index for position assignment
        for i in range(sides):
            # Compute start and end points for each side of the triangle with random rotation
            angle_start = i * 2 * np.pi / sides + random_rotation
            angle_end = (i + 1) * 2 * np.pi / sides + random_rotation
            start = np.array([np.cos(angle_start), np.sin(angle_start)]) * size / 2 + size / 2
            end = np.array([np.cos(angle_end), np.sin(angle_end)]) * size / 2 + size / 2
            # Assign points to the current side, adjust for additional points
            num_points_this_side = points_per_side + (1 if additional_points > 0 else 0)
            additional_points -= 1 if additional_points > 0 else 0
            # Distribute points linearly between start and end points
            positions[index:index + num_points_this_side] = np.linspace(start, end, num_points_this_side, endpoint=False)
            index += num_points_this_side
        positions = positions[:n_nodes]
    elif placement == 'rectangle':
        x = np.linspace(0, size, int(np.sqrt(n_nodes) + 1))
        y = np.linspace(0, size, int(np.sqrt(n_nodes) + 1))
        xv, yv = np.meshgrid(x, y)
        positions = np.column_stack((xv.ravel(), yv.ravel()))[:n_nodes]
    elif placement == 'line':
        num_lines = np.random.randint(1, 10)
        avg_speed = np.random.uniform(0.1, 20)  # Default speed in meters per second
        sampling_rate = np.random.randint(1, 100)  # Default sampling every second

        positions = []
        center_x, center_y = size / 2, size / 2  # Central point for all lines
        nodes_per_line = np.random.multinomial(n_nodes, [1 / num_lines] * num_lines)

        for i in range(num_lines):
            angle = np.random.uniform(0, 2 * np.pi)
            # Calculate the maximum distance that can be covered within the boundaries
            max_distance = calculate_maximum_distance(center_x, center_y, angle, size)
            total_distance = min(avg_speed * sampling_rate, max_distance)

            for j in range(nodes_per_line[i]):
                step = total_distance * (j / nodes_per_line[i])
                x = center_x + step * np.cos(angle)
                y = center_y + step * np.sin(angle)
                positions.append([x, y])

        positions = np.array(positions)
    else:
        raise ValueError("Unsupported placement type.")

    return positions



# Generate new position outside the range
def random_position_outside_sample(region, sampled_region):
    (x1, y1, x2, y2) = region  # Main rectangle coordinates
    (sx1, sy1, sx2, sy2) = sampled_region  # Sampled region coordinates

    while True:
        # Generate a random point within the main rectangle
        rand_x = random.uniform(x1, x2)
        rand_y = random.uniform(y1, y2)

        # Check if the point is outside the sampled region
        if not (sx1 <= rand_x <= sx2 and sy1 <= rand_y <= sy2):
            return (rand_x, rand_y)

# Initialize DataFrame to collect data
columns = ["num_samples", "node_positions", "node_rssi", "node_noise", "node_states", "jammer_position", "jammer_power", "jammer_gain", "pl_exp", "sigma"]
data_collection = pd.DataFrame(columns=columns)

# Node information
if ALL_JAMMED:
    instance_count, num_instances = 0, 5000
else:
    instance_count, num_instances = 0, 20000

if ENV == "fspl":
    loss_func = free_space_path_loss
    folder_path = "fspl"
else:
    loss_func = log_distance_path_loss
    folder_path = f"log_distance/{ENV}"

node_placement_strategy = ['random', 'circle', 'triangle', 'rectangle']
# node_placement_strategy = ['line']
for placement_strategy in node_placement_strategy:
    instance_count = 0
    if not ALL_JAMMED:
        data_collection = pd.DataFrame(columns=columns)
    while instance_count < num_instances:
        if instance_count < 10000:
            FREQUENCY = 2.4e9
        elif instance_count >= 10000:
            FREQUENCY = 5.0e9
        # Path loss variables for simulation of environment where the conditions are predominantly open with minimal obstructions
        if ENV == "urban_area":
            n = np.random.uniform(2.7, 3.5)
        elif ENV == "shadowed_urban_area":
            n = np.random.uniform(3.0, 5)
        elif ENV == "fspl":
            n = 2.0
        else:
            raise "Unknown environment"
        sigma = np.random.uniform(2, 6)  # Random shadow fading between 1 dB and 6 dB
        size = np.random.randint(500, 1500) # Area size in meters [500, 1500]
        lb_nodes = calculate_node_bounds(size)
        ub_nodes = 8 * lb_nodes
        beta_values = np.random.beta(2, 8)
        n_nodes = math.ceil(beta_values * (ub_nodes - lb_nodes) + lb_nodes)

        # Radio parammeters
        P_tx = np.random.randint(15, 30)  # Transmit power in dBm [15, 30]
        G_tx = 0  # Transmitting antenna gain in dBi [0, 5]
        G_rx = 0  # Receiving antenna gain in dBi [0, 5]
        P_tx_jammer = np.random.randint(20, 60)  # Jammer transmit power in dBm [25, 50]
        G_tx_jammer = np.random.randint(0, 5)  # Jammer transmitting antenna gain in dBi [0, 5]

        # Node positions
        node_positions = get_position(n_nodes, size, placement=placement_strategy)

        # Get the min and max values for x and y
        min_x, min_y = np.min(node_positions, axis=0)
        max_x, max_y = np.max(node_positions, axis=0)

        # Define the region and sampled region based on the min and max values of node positions
        region = (0, 0, 1500, 1500)
        sampled_region = (min_x, min_y, max_x, max_y)

        # Random jammer position
        if JAMMER_OUTSIDE_SAMPLE:
            jammer_position = random_position_outside_sample(region, sampled_region)
        else:
            # Generate jammer within the bounds of the sampled region S
            jammer_x = np.random.uniform(min_x, max_x)
            jammer_y = np.random.uniform(min_y, max_y)
            jammer_position = np.array([jammer_x, jammer_y])

            # # Generate jammer within 80% of the radius of the circle from the center
            # circle_center = np.array([size / 2, size / 2])  # Assuming the circle is centered at (size/2, size/2)
            # max_radius = size / 2 * 0.8  # 80% of the radius of the circle
            #
            # # Generate a random radius and angle
            # random_radius = np.random.uniform(0, max_radius)
            # random_angle = np.random.uniform(0, 2 * np.pi)
            #
            # # Convert polar coordinates to Cartesian coordinates
            # jammer_x = circle_center[0] + random_radius * np.cos(random_angle)
            # jammer_y = circle_center[1] + random_radius * np.sin(random_angle)
            #
            # jammer_position = np.array([jammer_x, jammer_y])

        config = {
            'size': size,
            'n_nodes': n_nodes,
            'P_tx': P_tx,
            'G_tx': G_tx,
            'G_rx': G_rx,
            'P_tx_jammer': P_tx_jammer,
            'G_tx_jammer': G_tx_jammer
        }

        # Distance calculations
        dist_matrix = np.linalg.norm(node_positions[:, np.newaxis, :] - node_positions[np.newaxis, :, :], axis=2)
        jammer_dist = np.linalg.norm(node_positions - jammer_position, axis=1)

        # Path loss calculations
        if loss_func == log_distance_path_loss:
            path_loss = loss_func(dist_matrix, n=n, sigma=sigma)
            path_loss_jammer = loss_func(jammer_dist, n=n, sigma=sigma)
        else:
            path_loss = loss_func(dist_matrix)
            path_loss_jammer = loss_func(jammer_dist)

        # RSSI calculations
        rssi_matrix = P_tx + G_tx + G_rx - path_loss
        rssi_jammer = P_tx_jammer + G_tx_jammer + G_rx - path_loss_jammer

        # Precompute maximum jammer RSSI for each pair using broadcasting
        # Sample alongwith path (i,j) and take the highest jamming power from those points to represent power at (i,j)
        max_jammer_rssi_matrix = np.full((n_nodes, n_nodes), -np.inf)  # Initialize with low values
        for i in range(n_nodes):
            for j in range(i + 1, n_nodes):  # Only fill upper triangle, the matrix is symmetric
                # Sample path and compute maximum jamming power
                # print("length of node pos: ", len(node_positions))
                # print("number of nodes: ", n_nodes)
                max_jamming_power_dbm = sample_path_jamming(node_positions[i], node_positions[j], jammer_position[0], loss_func, n, sigma)
                max_jammer_rssi_matrix[i, j] = max_jamming_power_dbm
                max_jammer_rssi_matrix[j, i] = max_jamming_power_dbm

        # Convert maximum jammer RSSI to linear scale for the entire matrix
        jammer_power_linear_matrix = dbm_to_linear(max_jammer_rssi_matrix)

        # Compute the noise floor for all pairs
        noise_floor_matrix = dbm_to_linear(NOISE_LEVEL) + jammer_power_linear_matrix

        # Convert RSSI values of the original matrix to linear scale
        rssi_linear_matrix = dbm_to_linear(rssi_matrix)

        # Compute SINR for all pairs
        sinr_matrix = rssi_linear_matrix / noise_floor_matrix

        # Convert SINR back to dB for the entire matrix
        sinr_db_matrix = linear_to_db(sinr_matrix)

        # Adjust the RSSI matrix
        rssi_affected_matrix = np.minimum(rssi_matrix, rssi_matrix - (REFERENCE_SINR - sinr_db_matrix))
        rssi_affected_matrix = np.maximum(rssi_affected_matrix, RSSI_THRESHOLD)

        # Ignore self-comparisons
        np.fill_diagonal(rssi_matrix, np.nan)
        np.fill_diagonal(rssi_affected_matrix, np.nan)

        # Calculate normal RSSI as the mean/max of the valid signals
        affected_rssi = np.nanmax(rssi_affected_matrix, axis=1)

        # Reference to disconnected nodes
        # disconnected = affected_rssi == np.nan
        disconnected = np.isnan(affected_rssi)
        # Calculate normal RSSI as the mean/max of the valid signals
        affected_rssi = np.nan_to_num(affected_rssi, nan=RSSI_THRESHOLD)  # Replace NaN with rssi_threshold or any suitable default (isolated samples)

        # Compute linear powers for jammer and normal signals
        P_rx_linear = dbm_to_linear(affected_rssi)
        N_linear = dbm_to_linear(NOISE_LEVEL)
        jammer_linear = dbm_to_linear(rssi_jammer)

        # Compute SINR in linear scale and convert SINR from linear scale to dB
        noise_floor = jammer_linear + N_linear
        noise_floor_dB = linear_to_db(noise_floor)

        SINR_linear = P_rx_linear / noise_floor
        SINR_dB = linear_to_db(SINR_linear)

        # Compute detection threshold for SINR
        jammed = noise_floor_dB > NOISE_THRESHOLD

        jammed_nodes = np.sum(jammed) >= 3  # At least 3 nodes are jammed (3 since current simulation is in 2D) # required for CJ testing
        not_jammed_nodes = np.sum(~jammed) >= 1  # At least 1 node is not jammed
        all_jammed_nodes = np.sum(~jammed) == 0  # All nodes are jammed
        high_rssi_nodes = np.sum(affected_rssi > -80) >= 1  # Ensure at least one node able to communicate with another node

        # Condition checks
        if ALL_JAMMED:
            conditions_met = all_jammed_nodes
        else:
            conditions_met = jammed_nodes and not_jammed_nodes and high_rssi_nodes

        if conditions_met:
            instance_count += 1
            print("instance count: ", instance_count)
            if PLOT:
                plot_network_with_rssi(node_positions, affected_rssi, jammer_position, SINR_dB, noise_floor_dB, jammed)

            # Data to be collected
            data = {
                "num_samples": n_nodes,
                "node_positions": [node_positions.tolist()],  # Convert positions to list for storage
                "node_rssi": [affected_rssi.tolist()],  # RSSI values converted to list
                "node_noise": [noise_floor_dB.tolist()],  # RSSI values converted to list
                "node_states": [jammed.astype(int).tolist()],  # Convert boolean array to int and then to list
                "jammer_position": [[jammer_position[0], jammer_position[1]]],  # Jammer position
                "jammer_power": P_tx_jammer,  # Jammer transmit power
                "jammer_gain": G_tx_jammer,  # Jammer gain
                "frequency": FREQUENCY,
                "pl_exp": n,  # Path loss exponent
                "sigma": sigma,  # Shadow fading
                "node_placement": placement_strategy,
                "jammer_outside_sample": JAMMER_OUTSIDE_SAMPLE
            }

            # Append the new row to the data collection DataFrame
            data_collection = pd.concat([data_collection, pd.DataFrame(data, index=[0])], ignore_index=True)

    # After the loop, save the DataFrame to a CSV file
    if not ALL_JAMMED:
        if JAMMER_OUTSIDE_SAMPLE:
            data_collection.to_csv(f"train_test_data/{folder_path}/{placement_strategy}_jammer_outside_region_INC_SAMPLES.csv", index=False)
        else:
            data_collection.to_csv(f"train_test_data/{folder_path}/{placement_strategy}_INC_SAMPLES.csv", index=False)

if ALL_JAMMED:
    # After the loop, save single DataFrame to a CSV file with each shape included
    if JAMMER_OUTSIDE_SAMPLE:
        data_collection.to_csv(f"train_test_data/{folder_path}/all_jammed_jammer_outside_region_INC_SAMPLES.csv", index=False)
    else:
        data_collection.to_csv(f"train_test_data/{folder_path}/all_jammed_INC_SAMPLES.csv", index=False)