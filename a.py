<<<<<<< HEAD
# -*- coding: utf-8 -*-
# UTF-8 encoding when using korean
def count(n, L, R, prices):
	psum = [0] * (n + 1)
	
	for i in range(n):
		psum[i+1] = psum[i] + prices[i]
	
	total = 0
	
	for a in range(1, n + 1):
		for b in range(a, n + 1):
    	sum_ab = psum[b] - psum[a - 1]
      if L <= sum_ab <= R:
      	total += 1
    
  return total
		
			

n,L,R = map(int, input().split())
prices = list(map(int, input().split()))


print(count(n,L,R,prices))
=======
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
>>>>>>> 39dff41fc9fbdb9518f7a05e88404319d3f6f5fd
