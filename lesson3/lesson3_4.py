import random


def play_game():
    min = 1
    max = 100

    count = 0
    target = random.randint(min,max) 
    print(target)
    print("=======猜數字遊戲=======\n")
    while(True):
        keyin = int(input(f"猜數字範圍{min}到{max}:\n"))
        count += 1
        if keyin >= min and keyin <= max:
            if target == keyin:
                print("中")
                print(f"您猜了{count}次")
                break
            
            elif(keyin > target):
                print("小一點")
                max = keyin-1

            elif(keyin < target):
                print("大一點")
                min = keyin+1

            print(f"您猜了{count}次")
            
        else:
            print("輸入提示範圍內的數字")


def main():
    while(True):
        
        play_game()
        is_play_again = input(f"您還要繼續嗎？y/n")

        if is_play_again == 'n':
            break

    print("遊戲結束")

if __name__ == "__main__":
    main()