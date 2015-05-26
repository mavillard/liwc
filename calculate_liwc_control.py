import csv
import sys


# $ python calculate_liwc.py score range
# 4 combinations:
# $ python calculate_liwc.py minmax minmax
# $ python calculate_liwc.py minmax 100
# $ python calculate_liwc.py subtraction minmax
# $ python calculate_liwc.py subtraction 100
LIWC_SCORE_OPT = sys.argv[1]
LIWC_RANGE_OPT = sys.argv[2]
assert(LIWC_SCORE_OPT == 'minmax' or LIWC_SCORE_OPT == 'subtraction')
assert(LIWC_RANGE_OPT == 'minmax' or LIWC_RANGE_OPT == '100')
print sys.argv

# Normalization
def scale(a, b, c, d): # [a, b] -> [c, d]
    def y(x):
        return (float(d - c) / (b - a)) * (x - a) + c
    return y

def normalize(a, b): # [a, b] -> [-1, +1]
    return scale(a, b, -1, 1)

# Auxiliar
def calculate_score(pos, neg, method):
    if method == 'subtraction':
        result = pos - neg
    else: # method == 'minmax'
        if pos == neg:
            result = 0
        else:
            result = max(pos, neg)
            if result == neg:
                result = -result
    return result

# Convert control_output.txt into control_output.csv
output_csv = open('control_output.csv', 'w')
output_csv.close()
output_csv = open('control_output.csv', 'a')
csv_writer = csv.writer(
    output_csv,
    delimiter=',',
    quotechar='"',
    quoting=csv.QUOTE_MINIMAL
)
output_txt = open('control_output.txt')
for line in output_txt:
    row = line.strip().split('\t')
    csv_writer.writerow(row)

output_txt.close()
output_csv.close()

# Calculate MINs and MAXs
outs = []
output = open('control_output.csv')
out_reader = csv.reader(
    output,
    delimiter=',',
    quotechar='"'
)
out_reader.next()
iters = 1
for out_row in out_reader:
    posemo = float(out_row[5])
    negemo = float(out_row[6])
    liwc = calculate_score(posemo, negemo, LIWC_SCORE_OPT)
    outs.append(liwc)
    iters += 1

output.close()

print min(outs)
print max(outs)

if LIWC_RANGE_OPT == '100':
    MIN_LIWC = -100
    MAX_LIWC = 100
else: # LIWC_RANGE_OPT == 'minmax'
    max_abs = max(abs(min(outs)), abs(max(outs)))
    MIN_LIWC = -max_abs
    MAX_LIWC = max_abs
MIN_SCORE = -2
MAX_SCORE = 2

# Join files
scores = open('control_scores.csv')
scr_reader = csv.reader(
    scores,
    delimiter=',',
    quotechar='"'
)

output = open('control_output.csv')
out_reader = csv.reader(
    output,
    delimiter=',',
    quotechar='"'
)

# $ python calculate_liwc.py score range
# 4 combinations:
# $ python calculate_liwc.py minmax minmax
# $ python calculate_liwc.py minmax 100
# $ python calculate_liwc.py subtraction minmax
# $ python calculate_liwc.py subtraction 100
if LIWC_SCORE_OPT == 'minmax' and LIWC_RANGE_OPT == 'minmax':
    RESULT_FILE = 'control_results_minmax_minmax.csv'
elif LIWC_SCORE_OPT == 'minmax' and LIWC_RANGE_OPT == '100':
    RESULT_FILE = 'control_results_minmax_100.csv'
elif LIWC_SCORE_OPT == 'subtraction' and LIWC_RANGE_OPT == 'minmax':
    RESULT_FILE = 'control_results_subtraction_minmax.csv'
else: # LIWC_SCORE_OPT == 'subtraction' or LIWC_RANGE_OPT == '100':
    RESULT_FILE = 'control_results_subtraction_100.csv'
result = open(RESULT_FILE, 'w')
res_writer = csv.writer(
    result,
    delimiter=',',
    quotechar='"',
    quoting=csv.QUOTE_MINIMAL
)
res_writer.writerow(['#s', 'sentence', 'score', 'liwc', 'norm_score', 'norm_liwc'])

scr_reader.next()
out_reader.next()
iters = 1
for scr_row, out_row in zip(scr_reader, out_reader):
    ns = out_row[2]
    sentence = scr_row[0]
    score = float(scr_row[1])
    posemo = float(out_row[5])
    negemo = float(out_row[6])
    liwc = calculate_score(posemo, negemo, LIWC_SCORE_OPT)
    norm_score = normalize(MIN_SCORE, MAX_SCORE)(score)
    norm_liwc = normalize(MIN_LIWC, MAX_LIWC)(liwc)
    res_writer.writerow([ns, sentence, score, liwc, norm_score, norm_liwc])
    iters += 1

scores.close()
output.close()
result.close()
