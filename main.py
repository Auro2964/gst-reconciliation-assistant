# n = int(input("enter a number "))
# sum=0
# for i in range(1,n):
#     if n%i==0:
#         sum+=i

# print(sum)

# if sum==n:
#     print("perfect no")
# else:
#     print('not')            


# n=int(input('enter a no. '))
# count=0
# for i in range(1,n+1):
#     if n%i==0:
#         count+=1

# if count == 2:
#     print('prime')
# else:
#     print('not')


# a="sbdc"
# b=""
# for i in range(len(a)-1,-1,-1):
#     b=b+a[i]


# if b==a:
#     print('yes pallindrome')
# else:
#     print('no')
    


a=int(input('enter a no. '))
rev=0
while a>0:
    rev=rev*10+a%10
    a//10
print(rev)