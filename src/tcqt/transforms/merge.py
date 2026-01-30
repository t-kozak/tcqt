"""
Merge utilities for combining multiple "Workplane" objects efficiently.

This module provides tree-based merging algorithms with optional multi-threading
for better performance when combining large numbers of shapes.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..workplane import Workplane

from ..dev_tools import tqdm


def merge_batch_worker(batch: list["Workplane"]) -> "Workplane | None":
    """
    Worker function to merge a single batch of shapes.

    Args:
        batch: List of "Workplane" objects to merge

    Returns:
        Merged "Workplane" or None if batch is empty
    """
    if not batch:
        return None

    if len(batch) == 1:
        return batch[0]

    try:
        merged_shape = batch[0]
        for shape in batch[1:]:
            merged_shape = merged_shape.union(shape)
        return merged_shape
    except Exception as e:
        print(f"Warning: Could not merge shapes in batch: {e}")
        # If merge fails, return the first shape as fallback
        return batch[0] if batch else None


def merge_shapes_in_batches(
    shapes: list["Workplane"], batch_size: int = 10
) -> "Workplane | None":
    """
    Merge shapes in batches using a tree-based approach for better performance.

    Args:
        shapes: List of "Workplane" objects to merge
        batch_size: Number of shapes to merge in each batch (default: 10)

    Returns:
        Single merged "Workplane" or None if no shapes provided
    """
    if not shapes:
        return None

    if len(shapes) == 1:
        return shapes[0]

    current_shapes = shapes.copy()

    while len(current_shapes) > 1:
        next_batch = []

        # Process shapes in batches
        for i in range(0, len(current_shapes), batch_size):
            batch = current_shapes[i : i + batch_size]

            if len(batch) == 1:
                # Single shape in batch, just add it to next batch
                next_batch.append(batch[0])
            else:
                # Merge multiple shapes in this batch
                merged_shape = merge_batch_worker(batch)
                if merged_shape is not None:
                    next_batch.append(merged_shape)

        current_shapes = next_batch

    return current_shapes[0] if current_shapes else None


def merge_shapes_in_batches_threaded(
    shapes: list["Workplane"],
    batch_size: int = 10,
    max_workers: int | None = None,
    show_progress: bool = False,
) -> "Workplane | None":
    """
    Merge shapes in batches using a tree-based approach with multi-threading for better performance.

    Args:
        shapes: List of "Workplane" objects to merge
        batch_size: Number of shapes to merge in each batch (default: 10)
        max_workers: Maximum number of worker threads (default: None for auto-detection)
        show_progress: Whether to show progress information

    Returns:
        Single merged "Workplane" or None if no shapes provided
    """
    if not shapes:
        return None

    if len(shapes) == 1:
        return shapes[0]

    # Use fewer workers for smaller datasets to avoid overhead
    if max_workers is None:
        cpu_count = os.cpu_count() or 4  # Fallback to 4 if cpu_count() returns None
        max_workers = min(cpu_count, max(1, len(shapes) // (batch_size * 2)))

    if show_progress:
        print(f"Using {max_workers} worker threads for merging")

    current_shapes = shapes.copy()
    iteration = 0

    while len(current_shapes) > 1:
        iteration += 1
        if show_progress:
            print(
                f"Threaded merge iteration {iteration}: processing {len(current_shapes)} shapes..."
            )

        # Create batches
        batches = []
        for i in range(0, len(current_shapes), batch_size):
            batch = current_shapes[i : i + batch_size]
            if batch:  # Only add non-empty batches
                batches.append(batch)

        # Process batches in parallel
        next_batch = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batch merge tasks
            future_to_batch = {
                executor.submit(merge_batch_worker, batch): batch for batch in batches
            }

            # Collect results as they complete with progress bar
            progress_desc = f"Merge iteration {iteration}"
            for future in tqdm(
                as_completed(future_to_batch),
                total=len(batches),
                desc=progress_desc,
                disable=not show_progress,
            ):
                try:
                    result = future.result()
                    if result is not None:
                        next_batch.append(result)
                except Exception as e:
                    batch = future_to_batch[future]
                    print(f"Warning: Failed to merge batch of {len(batch)} shapes: {e}")
                    # Add shapes from failed batch individually
                    next_batch.extend(batch)

        current_shapes = next_batch

    if show_progress:
        print(f"Threaded merging completed in {iteration} iterations")

    return current_shapes[0] if current_shapes else None
