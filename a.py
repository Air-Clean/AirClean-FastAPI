def evaluate_water_quality(data):
    evaluation = {}
    if(data == 'a'):
        evaluation['1'] = data
        evaluation['2'] = data
    else:
        evaluation['2'] = data
    print(evaluation)
evaluate_water_quality('a');
evaluate_water_quality('b');