class Player:
    def __init__(self, name, hp, mp, ap, dp, ):
        self.name = name
        self.hp = hp
        self.mp = mp
        self.ap = ap #攻撃力
        self.dp = dp #防御力
        self.alive = True        
    def attack(self, enemy): #通常攻撃
        damege = max(self.ap - enemy.dp // 2 + rnd(-5,6), 0 )
        enemy.hp = enemy.hp - damege
        print(f'{self.name}は{enemy.name}を攻撃した！')
        print(f'{damege}のダメージを与えた！')
        if enemy.hp < 1:
            self.alive = False        
            print(f'{enemy.name}はちからつきた！')
    def defence(self): #まもる
        print(f'{self.name}は身構えている！')       
    def display_status(self):
        print(f'{self.name}')
        print(f'HP:{self.hp}')
        print(f'MP:{self.mp}')
        print('---------------')
class Wizard(Player):
    def __init__(self, name):
        hp = 60 + rnd(-10,11)
        mp = 10 + rnd(-5,6)
        ap = 10 + rnd(-2,3)
        dp = 10 + rnd(-2,3)
        super().__init__(name, hp, mp, ap, dp)
    def attack_with_magic(self): #魔法攻撃
        print(f'{self.name}はメラを唱えた！')
        print(f'{1000000000}のダメージを与えた！')
        self.mp -= 1
class Warrior(Player):
    def __init__(self, name):
        hp = 100 + rnd(-10,11)
        mp = 0
        ap = 20 + rnd(-2,3)
        dp = 20 + rnd(-2,3)
        super().__init__(name, hp, mp, ap, dp)
    def attack_special(self): #特別攻撃
        print(f'{self.name}の全力をいちげき！')
        print(f'{self.ap*2}のダメージを与えた！')
class Monster:
    def __init__(self, name, hp, mp, ap, dp, ):
        self.name = name
        self.hp = hp
        self.mp = mp
        self.ap = ap #攻撃力
        self.dp = dp #防御力 
        self.alive = True
        print(f'{self.name}があらわれた！')
        
    def attack(self, enemy): #通常攻撃
        damege = max(self.ap - enemy.dp // 2 + rnd(-5,6), 0 )
        enemy.hp = enemy.hp - damege
        print(f'{self.name}は{enemy.name}を攻撃した！')
        print(f'{damege}のダメージを与えた！')
        if enemy.hp < 1:
            self.alive = False        
            print(f'{enemy.name}はちからつきた！')

    def do_nothing(self): #なにもしない
        print(f'{self.name}はようすをみている')

class Slime(Monster):
    def __init__(self, name):
        hp = 30
        mp = 0
        ap = 20
        dp = 0
        super().__init__(name, hp, mp, ap, dp)
    def run_away(self):
        print(f'{self.name}は逃げ出した！')
        #インスタンスの消去
        self.alive = False
class Gohst:
    pass