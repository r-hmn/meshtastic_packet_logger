clear
date >> main.log

# Activate virtual environment
source venv/bin/activate

# Must be unbuffered?..
python3 -u main.py |& tee -a main.log


