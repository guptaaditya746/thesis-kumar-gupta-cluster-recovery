#!/bin/bash
#SBATCH --job-name=docling_bench
#SBATCH --partition=gammaweb
#SBATCH --gres=gpu:hopper:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=10:10:00
#SBATCH --output=docling_bench_%j.log
#SBATCH --error=docling_bench_%j.err

echo "Starting Docling Benchmark Job at $(date)"

# 1. Navigate to the base directory and activate the environment
cd /mnt/ceph/storage/data-tmp/current/xepi3167/thesis/thesis-kumar-gupta/experiments/docling
source .venv/bin/activate

# 2. Move into the tutorial folder where the scripts live
cd tutorial

# 3. Set up the CSV file (saving it to the 'data' folder to keep things tidy)
CSV_FILE="../data/benchmark_results.csv"
echo "Script_Name,Time_Seconds" > "$CSV_FILE"

# 4. Define the list of scripts to run (excluding Mac OCR)
SCRIPTS=(
    "pypdfium_without_easyOCR.py"
    "pypdfium_with_easyOCR.py"
    "docling_without_easyOCR.py"
    "docling_easyOCR_with_GPU.py"
    "docling_easyOCR_with_CPU.py"
    "docling_parse_with_teserract.py"
    "docling_parse_with_teserract_cli.py"
)

# 5. Loop through, execute, and time each script
for script in "${SCRIPTS[@]}"; do
    echo "========================================"
    echo "Running $script..."
    
    # Capture start time (with nanosecond precision)
    start_time=$(date +%s.%N)
    
    # Execute the python script
    python "$script"
    
    # Capture end time
    end_time=$(date +%s.%N)
    
    # Calculate elapsed time using awk (which is always available on compute nodes)
    elapsed_time=$(awk "BEGIN {printf \"%.2f\", $end_time - $start_time}")
    
    # Write the result to the CSV
    echo "$script,$elapsed_time" >> "$CSV_FILE"
    echo "--> Finished $script in $elapsed_time seconds."
done

echo "========================================"
echo "All benchmarks complete! Results saved to $CSV_FILE"
echo "Job finished at $(date)"
