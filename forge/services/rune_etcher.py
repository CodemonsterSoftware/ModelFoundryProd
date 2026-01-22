import math
import logging
import struct
import numpy as np
import trimesh
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

class RuneEtcher:
    """
    A class for digitally watermarking STL files using various steganography techniques.
    """
    
    STRATEGY_VERTEX_PERMUTATION = 'vertex_permutation'
    STRATEGY_MICRON_SHIFTING = 'micron_shifting'
    STRATEGY_DEGENERATE_GEOMETRY = 'degenerate_geometry'
    STRATEGY_TOPOLOGICAL_SUBDIVISION = 'topological_subdivision'
    
    def __init__(self, strategy: str = STRATEGY_VERTEX_PERMUTATION):
        self.strategy = strategy

    def etch(self, input_path: str, output_path: str, message: str) -> bool:
        """
        Encode a message into an STL file.
        """
        try:
            # multiple strategies check
            if self.strategy == self.STRATEGY_VERTEX_PERMUTATION:
                return self._etch_vertex_permutation(input_path, output_path, message)
            elif self.strategy == self.STRATEGY_MICRON_SHIFTING:
                return self._etch_micron_shifting(input_path, output_path, message)
            elif self.strategy == self.STRATEGY_DEGENERATE_GEOMETRY:
                return self._etch_degenerate_geometry(input_path, output_path, message)
            elif self.strategy == self.STRATEGY_TOPOLOGICAL_SUBDIVISION:
                return self._etch_topological_subdivision(input_path, output_path, message)
            else:
                raise ValueError(f"Unknown strategy: {self.strategy}")
        except Exception as e:
            logger.error(f"Failed to etch rune: {e}")
            raise

    def read(self, input_path: str) -> str:
        """
        Decode a message from an STL file.
        """
        try:
            if self.strategy == self.STRATEGY_VERTEX_PERMUTATION:
                return self._read_vertex_permutation(input_path)
            elif self.strategy == self.STRATEGY_MICRON_SHIFTING:
                return self._read_micron_shifting(input_path)
            elif self.strategy == self.STRATEGY_DEGENERATE_GEOMETRY:
                return self._read_degenerate_geometry(input_path)
            elif self.strategy == self.STRATEGY_TOPOLOGICAL_SUBDIVISION:
                return self._read_topological_subdivision(input_path)
            else:
                raise ValueError(f"Unknown strategy: {self.strategy}")
        except Exception as e:
            logger.error(f"Failed to read rune: {e}")
            return ""

    # =========================================================================
    # Vertex Permutation Strategy
    # =========================================================================
    
    def _etch_vertex_permutation(self, input_path: str, output_path: str, message: str) -> bool:
        """
        Encodes data by reordering triangles.
        The message is converted to an integer, which selects a specific permutation
        of the triangles (lexicographically ordered by centroid or similar).
        """
        mesh = trimesh.load(input_path, process=False)
        
        if not isinstance(mesh, trimesh.Trimesh):
             raise ValueError("Input file must be a mesh (STL)")

        faces = mesh.faces
        vertices = mesh.vertices
        
        triangles = vertices[faces] # (N, 3, 3)
        
        triangles = triangles.astype(np.float32)
        flat_tris = triangles.reshape(-1, 9)
        
        dtype = [('v'+str(i), 'f4') for i in range(9)]
        structured_tris = flat_tris.view(dtype).flatten()
        
        canonical_indices = np.argsort(structured_tris) # Indices that sort the array
        
        msg_bytes = message.encode('utf-8')
        msg_int = int.from_bytes(msg_bytes, byteorder='big')
        
        num_faces = len(faces)
        
        available = list(canonical_indices)
        permutation = []
        
        temp_int = msg_int
        
        encoded_count = 0
        while temp_int > 0:
            if encoded_count >= num_faces:
                 raise ValueError("Message too long for this mesh")
            
            radix = num_faces - encoded_count
            selection_index = temp_int % radix
            temp_int = temp_int // radix
            
            selected_original_index = available.pop(selection_index)
            permutation.append(selected_original_index)
            encoded_count += 1
            
        permutation.extend(available)
        
        new_faces = faces[np.array(permutation)]
        
        new_mesh = trimesh.Trimesh(vertices=vertices, faces=new_faces, process=False)
        new_mesh.export(output_path)
        
        return True

    def _read_vertex_permutation(self, input_path: str) -> str:
        """
        Decodes data from triangle order.
        """
        mesh = trimesh.load(input_path, process=False)
        if not isinstance(mesh, trimesh.Trimesh):
             return "Error: Not a mesh"

        faces = mesh.faces
        vertices = mesh.vertices
        triangles = vertices[faces]
        
        triangles = triangles.astype(np.float32)
        
        flat_tris = triangles.reshape(-1, 9)
        
        num_faces = len(faces)
        
        dtype = [('v'+str(i), 'f4') for i in range(9)]
        structured_tris = flat_tris.view(dtype).flatten()
        
        sort_indices = np.argsort(structured_tris)
        ranks = np.argsort(sort_indices) 
        
        available_ranks = list(range(num_faces))
        
        msg_int = 0
        multiplier = 1
        
        digits = []
        
        scan_limit = min(num_faces, 5000) 
        if num_faces > 20000:
            logger.warning("Large mesh, rune reading might be slow")
            
        for i in range(num_faces):
            current_rank = ranks[i]
            
            try:
                idx = available_ranks.index(current_rank)
                available_ranks.pop(idx)
                digits.append((idx, num_faces - i))
            except ValueError:
                break
                
        total_int = 0
        current_multiplier = 1
        
        for digit, radix in digits:
            total_int += digit * current_multiplier
            current_multiplier *= radix
            
        try:
            bit_len = total_int.bit_length()
            byte_len = (bit_len + 7) // 8
            if byte_len == 0:
                return ""
            decoded_bytes = total_int.to_bytes(byte_len, byteorder='big')
            
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            return f"<Invalid Rune Data>"

    # =========================================================================
    # Micron Shifting Strategy
    # =========================================================================

    def _etch_micron_shifting(self, input_path: str, output_path: str, message: str) -> bool:
        """
        Encodes data by modifying LSB of vertex coordinates.
        """
        mesh = trimesh.load(input_path, process=False)
        if not isinstance(mesh, trimesh.Trimesh):
             raise ValueError("Input file must be a mesh (STL)")

        vertices = mesh.vertices.copy() # (N, 3) float32
        
        flat_verts = vertices.reshape(-1)
        
        flat_verts_32 = flat_verts.astype(np.float32)
        int_view = flat_verts_32.view(np.int32)
        
        msg_bytes = message.encode('utf-8')
        msg_bytes += b'\0'
        
        bits = []
        for byte in msg_bytes:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
                
        if len(bits) > len(int_view):
            raise ValueError(f"Message too long. capacity={len(int_view)} bits, needed={len(bits)} bits")
            
        for i, bit in enumerate(bits):
            int_view[i] &= ~1
            int_view[i] |= bit
            
        new_vertices = flat_verts_32.reshape(-1, 3)
        
        new_mesh = trimesh.Trimesh(vertices=new_vertices, faces=mesh.faces, process=False)
        new_mesh.export(output_path)
        
        return True

    def _read_micron_shifting(self, input_path: str) -> str:
        """
        Decodes data from LSB of vertex coordinates.
        """
        mesh = trimesh.load(input_path, process=False)
        if not isinstance(mesh, trimesh.Trimesh):
             return "Error: Not a mesh"
             
        vertices = mesh.vertices.astype(np.float32)
        flat_verts = vertices.reshape(-1)
        int_view = flat_verts.view(np.int32)
        
        collected_bytes = bytearray()
        
        lsbs = int_view & 1
        
        num_bytes = len(lsbs) // 8
        lsbs_matrix = lsbs[:num_bytes*8].reshape(-1, 8)
        
        powers_of_two = np.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=np.int32)
        packed_bytes = np.dot(lsbs_matrix, powers_of_two)
        
        byte_data = packed_bytes.astype(np.uint8).tobytes()
        
        null_index = byte_data.find(b'\0')
        if null_index != -1:
            byte_data = byte_data[:null_index]
            
        try:
            return byte_data.decode('utf-8')
        except UnicodeDecodeError:
            return "<Invalid Rune Data - Garbage Found>"

    # =========================================================================
    # Degenerate Geometry Strategy
    # =========================================================================

    def _etch_degenerate_geometry(self, input_path: str, output_path: str, message: str) -> bool:
        """
        Encodes data by appending zero-area triangles.
        Triangle format: (x=char, y=0, z=0), (x=char, y=0, z=0), (x=char, y=0, z=0)
        """
        mesh = trimesh.load(input_path, process=False)
        if not isinstance(mesh, trimesh.Trimesh):
             raise ValueError("Input file must be a mesh (STL)")

        msg_bytes = message.encode('utf-8')
        
        new_verts = []
        new_faces = []
        start_idx = len(mesh.vertices)
        
        for i, byte in enumerate(msg_bytes):
            val = float(byte)
            v = [val, 0.0, 0.0]
            new_verts.append(v)
            new_verts.append(v)
            new_verts.append(v)
            
            base = start_idx + (i * 3)
            new_faces.append([base, base+1, base+2])
            
        final_verts = np.vstack([mesh.vertices, np.array(new_verts)])
        final_faces = np.vstack([mesh.faces, np.array(new_faces)])
        
        new_mesh = trimesh.Trimesh(vertices=final_verts, faces=final_faces, process=False)
        new_mesh.export(output_path)
        
        return True

    def _read_degenerate_geometry(self, input_path: str) -> str:
        """
        Decodes data from zero-area triangles.
        """
        mesh = trimesh.load(input_path, process=False)
        
        vertices = mesh.vertices
        faces = mesh.faces
        
        tris = vertices[faces]
        edge1 = tris[:, 1] - tris[:, 0]
        edge2 = tris[:, 2] - tris[:, 0]
        cross = np.cross(edge1, edge2)
        areas = 0.5 * np.linalg.norm(cross, axis=1)
        
        degenerate_indices = np.where(areas < 1e-6)[0]
        
        if len(degenerate_indices) == 0:
            return ""
            
        degenerate_tris = tris[degenerate_indices]
        
        msg_bytes = bytearray()
        
        for i in range(len(degenerate_indices)):
            tri = degenerate_tris[i]
            if np.allclose(tri[0], tri[1]) and np.allclose(tri[0], tri[2]):
                if abs(tri[0][1]) < 1e-6 and abs(tri[0][2]) < 1e-6:
                    val = int(round(tri[0][0]))
                    if 0 <= val <= 255:
                        msg_bytes.append(val)
                        
        try:
            return msg_bytes.decode('utf-8')
        except:
            return "<Invalid Rune Data>"

    # =========================================================================
    # Topological Subdivision Strategy
    # =========================================================================

    def _etch_topological_subdivision(self, input_path: str, output_path: str, message: str) -> bool:
        """
        Encodes data by splitting faces to manipulate parity count in a grid.
        32-bit width grid (e.g. 4x4x4 = 64 cells).
        We encode bits into the parity of face counts in each cell.
        """
        mesh = trimesh.load(input_path, process=False)
        if not isinstance(mesh, trimesh.Trimesh):
             raise ValueError("Input file must be a mesh (STL)")
             
        bounds = mesh.bounds
        size = bounds[1] - bounds[0]
        origin = bounds[0]
        
        size = size * 1.01
        
        GRID_dim = 4
        cells = GRID_dim ** 3 
        
        msg_bytes = message.encode('utf-8')
        bits = []
        for byte in msg_bytes:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        
        if len(bits) > cells:
             raise ValueError(f"Message too long for topological grid (max {cells} bits)")
             
        centroids = mesh.triangles_center
        
        norm_coords = (centroids - origin) / size
        
        indices = (norm_coords * GRID_dim).astype(int)
        indices = np.clip(indices, 0, GRID_dim - 1)
        
        flat_indices = indices[:, 0] * (GRID_dim*GRID_dim) + indices[:, 1] * GRID_dim + indices[:, 2]
        
        # Count vertices (not faces) per cell
        verts = mesh.vertices
        norm_v = (verts - origin) / size
        idx_v = (norm_v * GRID_dim).astype(int)
        idx_v = np.clip(idx_v, 0, GRID_dim - 1)
        flat_idx_v = idx_v[:, 0] * (GRID_dim*GRID_dim) + idx_v[:, 1] * GRID_dim + idx_v[:, 2]
        
        counts = np.bincount(flat_idx_v, minlength=cells) # Vertex counts
        
        faces_to_split = []
        
        # Calculate Parity and Diff
        for i, bit in enumerate(bits):
            current_count = counts[i]
            current_parity = current_count % 2
            
            if current_parity != bit:
                # We need to flip Vertex Parity
                # Face Poke (1->3 faces) adds 1 Vertex (Centroid).
                # So Face Poke flips Vertex Parity. Perfect.
                
                # Find a candidate face in this cell to Poke
                # Mapping faces to cells (by centroid)
                cell_face_indices = np.where(flat_indices == i)[0]
                if len(cell_face_indices) > 0:
                    target_face_idx = cell_face_indices[0]
                    faces_to_split.append(target_face_idx)
                else:
                    pass
        
        if not faces_to_split:
            mesh.export(output_path)
            return True
            
        old_faces = mesh.faces
        old_vertices = mesh.vertices
        
        faces_to_remove = set(faces_to_split)
        
        new_faces_list = []
        new_vertices_list = list(old_vertices)
        
        current_vert_count = len(old_vertices)
        
        for i in range(len(old_faces)):
            if i in faces_to_remove:
                f = old_faces[i]
                vA = old_vertices[f[0]]
                vB = old_vertices[f[1]]
                vC = old_vertices[f[2]]
                
                vP = (vA + vB + vC) / 3.0
                new_vertices_list.append(vP)
                p_idx = current_vert_count
                current_vert_count += 1
                
                new_faces_list.append([f[0], f[1], p_idx])
                new_faces_list.append([f[1], f[2], p_idx])
                new_faces_list.append([f[2], f[0], p_idx])
            else:
                new_faces_list.append(old_faces[i])
                
        new_mesh = trimesh.Trimesh(vertices=new_vertices_list, faces=new_faces_list, process=False)
        new_mesh.export(output_path)
        return True

    def _read_topological_subdivision(self, input_path: str) -> str:
        """
        Decodes data by detecting poked faces in grid cells.
        """
        mesh = trimesh.load(input_path, process=False)
        
        bounds = mesh.bounds
        size = bounds[1] - bounds[0]
        origin = bounds[0]
        size = size * 1.01
        GRID_dim = 4
        cells = GRID_dim ** 3
        
        # We need a robust way to detect Pokes.
        # But wait, original plan:
        # Poked face ADDS faces. Count increases.
        # So we just read Parities of the counts.
        # We don't need to detect Pokes specifically!
        # The encoding "Poke" operation was chosen because it adds +2 faces (odd). 
        # Wait. 1 face -> 3 faces is +2 faces.
        # If Old Count = Even. New Count = Even + 2 = Even.
        # PARITY DOES NOT CHANGE WITH POKE (1->3).
        # I realized this in the comments earlier but proposed 1->4.
        # Then I implemented 1->3 (Poke).
        # So my implementation of etch_topological_subdivision adds 2 faces, so PARITY IS UNCHANGED.
        # The code is broken logically!
        
        # FIX: We need 1->4 split (Centre + 3 Edge Midpoints).
        # 1 Face -> 4 Faces. Change = +3 (Odd). Parity Flips.
        
        # But 1->4 split is hard because of shared edges.
        
        # Alternative: Just ADD a degenerate face to the cell?
        # That adds +1 count.
        # But degenerate faces might be stripped or confusing with the other strategy.
        # And user asked for "Topological Subdivision".
        
        # Let's go with "Poke" but count VERTICES in the cell?
        # 1->3 Poke adds 1 Vertex (Centroid).
        # Vertex count parity flips!
        # Yes! Count Vertices in the cell.
        
        centroids = mesh.triangles_center
        # But vertices don't have centroids in the same way faces do.
        # We map vertices to cells.
        
        verts = mesh.vertices
        norm_v = (verts - origin) / size
        idx_v = (norm_v * GRID_dim).astype(int)
        idx_v = np.clip(idx_v, 0, GRID_dim - 1)
        flat_idx_v = idx_v[:, 0] * (GRID_dim*GRID_dim) + idx_v[:, 1] * GRID_dim + idx_v[:, 2]
        
        counts = np.bincount(flat_idx_v, minlength=cells) # Vertex counts
        
        # But wait, to modify vertex count parity, we add 1 vertex.
        # Face Poke (1->3) adds exactly 1 vertex (the centroid).
        # So Face Poke FLIPS Vertex Count Parity.
        
        # So we should use Vertex Count Parity!
        
        # Let's check Etch logic:
        # "If current_parity != bit:"
        # We checked FACE count parity.
        # We need to check VERTEX count parity.
        
        # Re-implementing _read to use VERTEX count parity
        # And updating _etch to use VERTEX count parity.
        
        byte_array = bytearray()
        current_byte = 0
        
        cells_count = GRID_dim ** 3
        
        # We assume _etch was corrected to check vertex counts.
        # But _etch is already written above. I need to fix it.
        # I will update the logic below in this file.
        
        # Correct logic for Reading:
        byte_array = bytearray()
        current_byte = 0
        
        for i in range(cells_count):
             # Use Vertex Count Parity
             count = counts[i]
             bit = count % 2
             
             logger.info(f"Cell {i}: count={count}, bit={bit}")
             
             byte_idx = i // 8
             bit_idx = i % 8
             
             if bit:
                 current_byte |= (1 << (7 - bit_idx))
             
             if bit_idx == 7:
                  byte_array.append(current_byte)
                  current_byte = 0
                  
        null_idx = byte_array.find(b'\0')
        if null_idx != -1:
            byte_array = byte_array[:null_idx]
            
        try:
            return byte_array.decode('utf-8')
        except:
            return "<Invalid or Empty Rune>"