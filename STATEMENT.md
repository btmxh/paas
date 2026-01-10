# Project Assignment and Scheduling

A project consists of N tasks 1, 2, . . . , N need to be completed by M teams
1, 2, . . . , M. Team j is available at time point s(j). A task i has a duration
d(i) and can be performed by some teams: c(i,j) is the cost if team j
performs the task i. Between N tasks, there are precedence constraints
represented by Q pairs (i,j) in which task j can only be started to execute
after the completion of task i.
• Compute the schedule for performing N tasks (assign a team for each task
and specify the starting time-point for each that task) optimizing following
criteria (prioritize in the given order):
1.Number of tasks are scheduled is maximal
2.The completion time of all tasks is minimal
3.The total cost for the task assignment is minimal

Input
• Line 1: contains 2 integers N and Q (1 ≤ N,Q ≤ 1000)
• Line i + 1 (i = 1, 2, . . . ,Q): contains i and j in which task j can only be started to
execute after the completion of task i
• Line Q + 2: contains N positive integers d(1), d(2), . . . , d(N) (1 ≤ d(i) ≤ 1000)
• Line Q + 3: contains a positive integer M (1 ≤ M ≤ 500)
• Line Q + 4: contains M positive integers s(1), s(2), . . . , s(M) (1 ≤ s(i) ≤ 1000)
• Line Q + 5: contains a positive integer K (1 ≤ K ≤ 1000000)
• Line Q + 5 + k (k = 1, 2, ... ,K): contains i,j, and c(i,j) in which c(i,j) is the cost
when assigning team j to task i

• Output
• Line 1: contains a positive integer R
• Line i + 1 (i = 1, . . . , R): contains 3 positive integer i,j, and u in which task i is
assigned to team j and is started to execute at time-point u

Example
• Input
5 4
1 2
1 4
2 5
3 5
60 45 120 150 20
6
100 20 65 40 25 90
13
1 4 20

1 5 30
1 6 10
2 2 25
2 5 30
3 1 20
3 6 70
4 2 10
4 3 10
4 5 20
5 1 40

5 2 20
5 5 10
• Output
5
1 5 25
2 2 85
3 6 90
4 3 85
5 5 210
