import discord
from discord import app_commands
from discord.ext import commands
import random
import re
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- [이름 정제 함수] ---
def clean_name(member: discord.Member) -> str:
    """닉네임에서 이모지 및 특수문자를 제거하고 한글, 영문, 숫자만 남깁니다."""
    name = member.display_name or member.global_name or member.name
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9]', '', name)
    if not cleaned:
        cleaned = "".join(c for c in name if c.isalnum())
    if not cleaned:
        cleaned = f"User_{member.id % 1000}"
    return cleaned

# --- [게임 로직 클래스] ---
class BuckshotGame:
    def __init__(self, players):
        self.players = players
        self.max_hp = 5 if len(players) == 2 else 4
        self.hp = {p: self.max_hp for p in players}
        self.items = {p: [] for p in players}
        self.alive_players = players[:]
        random.shuffle(self.alive_players)
        self.current_idx = 0
        self.direction = 1  # 1: 순방향, -1: 역방향
        self.shells = []
        self.load_info_text = ""
        self.dmg = 1
        self.skip_list = [] 
        self.initial_setup()

    @property
    def current_player(self):
        return self.alive_players[self.current_idx]

    def initial_setup(self):
        total = random.randint(min(len(self.alive_players) + 1, 8), 8)
        live = random.randint(1, total - 1)
        blank = total - live
        self.shells = ['🔴 실탄'] * live + ['⚪ 공포탄'] * blank
        random.shuffle(self.shells)
        self.load_info_text = f"📢 **장전 완료:** 실탄 {live}발, 공포탄 {blank}발"
        
        # [수정된 부분] 2인 게임 시작 시에만 리모컨 제외
        item_list = ['🔍 돋보기', '🚬 담배', '🪚 톱', '⛓️‍💥 수갑', '💊 상한 약', '🎛️ 변환기', '💉 아드레날린']
        if len(self.alive_players) > 2:
            item_list.append('🎮 리모컨')

        for p in self.alive_players:
            for _ in range(2):
                if len(self.items[p]) < 6:
                    self.items[p].append(random.choice(item_list))

    def next_turn(self, shot_fired=False, current_player_removed=False):
        if shot_fired: 
            self.load_info_text = "📢 **장전 정보 비공개**"
        self.dmg = 1
        
        if len(self.alive_players) <= 1:
            return
            
        # [수정된 부분] 턴 계산 로직 단순화 및 안전화
        if not current_player_removed:
            self.current_idx = (self.current_idx + self.direction) % len(self.alive_players)
        else:
            self.current_idx %= len(self.alive_players)

        # 스킵 처리
        limit = len(self.alive_players)
        count = 0
        while self.alive_players[self.current_idx] in self.skip_list and count < limit:
            self.skip_list.remove(self.alive_players[self.current_idx])
            self.current_idx = (self.current_idx + self.direction) % len(self.alive_players)
            count += 1

# --- [메인 뷰: 메인 메뉴] ---
class BuckshotView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        self.main_message = None

    def create_embed(self, action_text):
        remaining_shells = len(self.game.shells)
        desc = f"{self.game.load_info_text}\n"
        desc += f"📦 **남은 총탄:** {remaining_shells}발\n"
        desc += f"---------------------------------------\n\n"
        desc += f"{action_text}\n"

        embed = discord.Embed(title="-----------------🏴‍☠️------------------", 
                              description=desc, 
                              color=discord.Color.dark_red())
        
        # 각 플레이어의 정보를 '필드(Field)'로 분리하여 추가합니다.
        for i, p in enumerate(self.game.players):
            hp_val = self.game.hp[p]
            hp_bar = "❤️" * max(0, hp_val) + "🖤" * (self.game.max_hp - max(0, hp_val))
            handcuff = "⛓️‍💥" if p in self.game.skip_list else ""
            
            if hp_val > 0:
                if self.game.items[p]:
                    emojis_only = " ".join([item.split(" ")[0] for item in self.game.items[p]])
                    item_str = f"`{emojis_only}`"
                else:
                    item_str = f"`아이템 없음`"
            else:
                item_str = f"`🪦 사망`"
            
            item_str += "ㅤㅤ"
            
            embed.add_field(
                name=f"{clean_name(p)}: {hp_bar} {handcuff}", 
                value=item_str, 
                inline=True
            )
            
            # 2명마다 무조건 빈 투명 칸막이(\u200b)를 넣어서 3번째 자리를 채워줍니다.
            if (i + 1) % 2 == 0:
                embed.add_field(name="\u200b", value="\u200b", inline=True)

        if len(self.game.alive_players) <= 1:
            embed.set_footer(text="🏁 게임 종료")
        else:
            embed.set_footer(text=f"현재 턴: {clean_name(self.game.current_player)}")
            
        return embed

    async def check_user(self, interaction: discord.Interaction):
        if not self.game.alive_players:
            await interaction.response.send_message("🏁 이미 종료된 게임입니다.", ephemeral=True)
            return False
            
        try:
            current_p = self.game.current_player
        except IndexError:
            await interaction.response.send_message("⏳ 게임 상태를 동기화 중입니다. 잠시 후 다시 시도해 주세요.", ephemeral=True)
            return False

        if interaction.user != current_p:
            await interaction.response.send_message("⏳ 당신의 턴이 아닙니다!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="자신 쏘기", style=discord.ButtonStyle.primary, row=0)
    async def shoot_self(self, interaction: discord.Interaction, button: discord.ui.Button):
        # (기존 코드와 동일)
        if not await self.check_user(interaction): return
        shell = self.game.shells.pop(0)
        p_died = False
        u_name = clean_name(interaction.user)
        if shell == '🔴 실탄':
            self.game.hp[interaction.user] -= self.game.dmg
            res = f"💥 **탕!** **{u_name}**님이 자신에게 **실탄**({self.game.dmg}뎀)을 쐈습니다!"
            if self.game.hp[interaction.user] <= 0: 
                self.game.alive_players.remove(interaction.user)
                p_died = True
            self.game.next_turn(shot_fired=True, current_player_removed=p_died)
        else:
            res = f"💨 **탕!** 공포탄입니다! **{u_name}**님은 턴을 유지합니다."
            self.game.load_info_text = "📢 **장전 정보 비공개**"
            self.game.dmg = 1
        await self.update_game_state(interaction, res)

    @discord.ui.button(label="상대 쏘기", style=discord.ButtonStyle.danger, row=0)
    async def shoot_other(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        targets = [p for p in self.game.alive_players if p != interaction.user]
        u_name = clean_name(interaction.user)
        
        if len(targets) == 1:
            target = targets[0]
            t_name = clean_name(target)
            shell = self.game.shells.pop(0)
            
            is_dead = False # [수정된 부분] 사망 여부 변수 추가
            if shell == '🔴 실탄':
                self.game.hp[target] -= self.game.dmg
                res = f"💥 **탕!** **{t_name}**님이 **{u_name}**님의 **실탄**({self.game.dmg}뎀)에 맞았습니다!"
                if self.game.hp[target] <= 0: 
                    self.game.alive_players.remove(target)
                    is_dead = True # 사망 시 True
            else:
                res = f"💨 **탕!** **{t_name}**님은 *공포탄*에 맞았습니다!"
                
            # [수정된 부분] is_dead를 전달
            self.game.next_turn(shot_fired=True, current_player_removed=is_dead)
            await self.update_game_state(interaction, res)
        else:
            await interaction.response.edit_message(view=TargetSelectView(self.game, self, "shoot"))

    @discord.ui.button(label="아이템 사용", style=discord.ButtonStyle.success, row=0)
    async def use_item_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # (기존 코드와 동일)
        if not await self.check_user(interaction): return
        if not self.game.items[interaction.user]:
            return await interaction.response.send_message("🎒 가방이 비어있습니다!", ephemeral=True)
        await interaction.response.edit_message(view=ItemSelectView(self.game, self))

    async def update_game_state(self, interaction, res_text, view_to_use=None):
        # (기존 코드와 동일)
        if view_to_use is None:
            view_to_use = self

        if len(self.game.alive_players) <= 1:
            winner = self.game.alive_players[0] if self.game.alive_players else self.game.players[0]
            res_text += f"\n\n🏆 **최종 승리자: {clean_name(winner)}**"
            return await interaction.response.edit_message(embed=self.create_embed(res_text), view=None)

        if not self.game.shells:
            self.game.initial_setup()
            res_text += "\n\n🔄 **재장전 및 아이템 보급 완료.**"
        
        await interaction.response.edit_message(embed=self.create_embed(res_text), view=view_to_use)

# --- [인라인 뷰: 대상 선택] ---
class TargetSelectView(discord.ui.View):
    def __init__(self, game, parent_view, action_type, item_idx=None, extra_info=None):
        super().__init__(timeout=60)
        self.game = game
        self.parent_view = parent_view
        self.action_type = action_type
        self.item_idx = item_idx
        self.extra_info = extra_info
        self.add_targets()

    def add_targets(self):
        for p in [tp for tp in self.game.alive_players if tp != self.game.current_player]:
            btn = discord.ui.Button(label=clean_name(p), style=discord.ButtonStyle.danger)
            btn.callback = self.create_callback(p)
            self.add_item(btn)
        
        cancel = discord.ui.Button(label="취소", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)

    def create_callback(self, target):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.game.current_player: return
            u_name = clean_name(interaction.user)
            t_name = clean_name(target)
            
            if self.action_type == "shoot":
                shell = self.game.shells.pop(0)
                if shell == '🔴 실탄':
                    self.game.hp[target] -= self.game.dmg
                    res = f"💥 **탕!** **{t_name}**님이 **{u_name}**님의 **실탄**에 맞았습니다!"
                    if self.game.hp[target] <= 0: self.game.alive_players.remove(target)
                else:
                    res = f"💨 **탕!** **{t_name}**님은 *공포탄*에 맞았습니다!"
                self.game.next_turn(shot_fired=True, current_player_removed=False)
            elif self.action_type == "handcuff":
                self.game.items[interaction.user].pop(self.item_idx)
                if target not in self.game.skip_list: self.game.skip_list.append(target)
                res = f"⛓️‍💥 **{u_name}**님이 **{t_name}**님에게 수갑을 채웠습니다!"
            elif self.action_type == "adrenaline_handcuff":
                if target not in self.game.skip_list: self.game.skip_list.append(target)
                res = f"💉 **{u_name}**님이 **{self.extra_info}**님의 수갑을 훔쳐 **{t_name}**님에게 채웠습니다!"
            
            await self.parent_view.update_game_state(interaction, res)
        return callback

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player: return
        await interaction.response.edit_message(view=self.parent_view)

# --- [인라인 뷰: 아이템 선택] ---
class ItemSelectView(discord.ui.View):
    def __init__(self, game, parent_view):
        super().__init__(timeout=60)
        self.game = game
        self.parent_view = parent_view
        self.add_item_buttons()

    def add_item_buttons(self):
        for i, name in enumerate(self.game.items[self.game.current_player]):
            btn = discord.ui.Button(label=name, style=discord.ButtonStyle.success)
            btn.callback = self.create_item_callback(i, name)
            self.add_item(btn)
        
        cancel = discord.ui.Button(label="뒤로가기", style=discord.ButtonStyle.secondary)
        cancel.callback = self.back_callback
        self.add_item(cancel)

    def create_item_callback(self, idx, item_name):
        async def callback(interaction: discord.Interaction):
            if not self.game.alive_players: return
            try:
                curr_player = self.game.current_player
            except IndexError:
                return
                
            if interaction.user != curr_player: return
            
            u_name = clean_name(interaction.user)
            
            if '🔍' in item_name:
                self.game.items[interaction.user].pop(idx)
                # 에페메럴 메시지로 본인에게만 탄환을 보여주고, 메인 메시지는 Interaction 실패 없이 안전하게 업데이트합니다.
                await interaction.response.send_message(f"🔍 현재 장전된 탄환은 **{self.game.shells[0]}**입니다.", ephemeral=True)
                await self.parent_view.main_message.edit(embed=self.parent_view.create_embed(f"🔍 **{u_name}**님이 돋보기를 사용했습니다."), view=self.parent_view)
                return # 아래의 부모 뷰 업데이트 중복 호출 방지
                
            elif '🚬' in item_name:
                self.game.items[interaction.user].pop(idx)
                self.game.hp[interaction.user] = min(self.game.max_hp, self.game.hp[interaction.user] + 1)
                await self.parent_view.update_game_state(interaction, f"🚬 **{u_name}**님이 체력을 회복했습니다.")
            elif '🪚' in item_name:
                self.game.items[interaction.user].pop(idx)
                self.game.dmg = 2
                await self.parent_view.update_game_state(interaction, f"🪚 **{u_name}**님이 총구를 잘랐습니다!")
            elif '⛓️‍💥' in item_name:
                targets = [p for p in self.game.alive_players if p != interaction.user]
                if len(targets) == 1:
                    self.game.items[interaction.user].pop(idx)
                    if targets[0] not in self.game.skip_list: self.game.skip_list.append(targets[0])
                    await self.parent_view.update_game_state(interaction, f"⛓️‍💥 **{u_name}**님이 **{clean_name(targets[0])}**님에게 수갑을 채웠습니다.")
                else:
                    await interaction.response.edit_message(view=TargetSelectView(self.game, self.parent_view, "handcuff", item_idx=idx))
            elif '💊' in item_name:
                self.game.items[interaction.user].pop(idx)
                p_died = False
                if random.choice([True, False]):
                    self.game.hp[interaction.user] = min(self.game.max_hp, self.game.hp[interaction.user] + 2)
                    res = f"💊 **{u_name}**님이 상한 약을 삼켰습니다!\n🤩 **대성공:** 체력을 2칸 회복합니다!"
                else:
                    self.game.hp[interaction.user] -= 1
                    res = f"💊 **{u_name}**님이 상한 약을 삼켰습니다!\n🤢 **부작용:** 체력을 1칸 잃었습니다."
                    if self.game.hp[interaction.user] <= 0:
                        self.game.alive_players.remove(interaction.user)
                        p_died = True
                        self.game.next_turn(current_player_removed=True)
                await self.parent_view.update_game_state(interaction, res)
            elif '🎛️' in item_name:
                self.game.items[interaction.user].pop(idx)
                current_shell = self.game.shells[0]
                self.game.shells[0] = '⚪ 공포탄' if current_shell == '🔴 실탄' else '🔴 실탄'
                await self.parent_view.update_game_state(interaction, f"🎛️ **{u_name}**님이 변환기를 작동하여 현재 탄환의 성질을 반대로 바꿨습니다!")
            elif '🎮' in item_name:
                self.game.items[interaction.user].pop(idx)
                self.game.direction *= -1
                await self.parent_view.update_game_state(interaction, f"🎮 **{u_name}**님이 리모컨을 작동했습니다! 이제 턴의 순서 방향이 반대로 뒤집힙니다.")
            elif '💉' in item_name:
                await interaction.response.edit_message(view=AdrenalineTargetView(self.game, self.parent_view, idx))
                
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player: return
        await interaction.response.edit_message(view=self.parent_view)

# --- [인라인 뷰: 아드레날린 대상 선택] ---
class AdrenalineTargetView(discord.ui.View):
    def __init__(self, game, parent_view, adrenaline_idx):
        super().__init__(timeout=60)
        self.game = game
        self.parent_view = parent_view
        self.adrenaline_idx = adrenaline_idx
        self.add_targets()

    def add_targets(self):
        for p in [tp for tp in self.game.alive_players if tp != self.game.current_player]:
            btn = discord.ui.Button(label=f"{clean_name(p)} ({len(self.game.items[p])}개)", style=discord.ButtonStyle.danger)
            btn.callback = self.create_callback(p)
            self.add_item(btn)
        
        cancel = discord.ui.Button(label="취소", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)

    def create_callback(self, target):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.game.current_player: return
            if not self.game.items[target]:
                await interaction.response.send_message("🎒 그 상대는 가방이 텅 비어있습니다!", ephemeral=True)
                return
            await interaction.response.edit_message(view=AdrenalineItemView(self.game, self.parent_view, target, self.adrenaline_idx))
        return callback

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player: return
        await interaction.response.edit_message(view=ItemSelectView(self.game, self.parent_view))

# --- [인라인 뷰: 아드레날린 아이템 강탈 및 즉시 시전] ---
class AdrenalineItemView(discord.ui.View):
    def __init__(self, game, parent_view, target, adrenaline_idx):
        super().__init__(timeout=60)
        self.game = game
        self.parent_view = parent_view
        self.target = target
        self.adrenaline_idx = adrenaline_idx
        self.add_item_buttons()

    def add_item_buttons(self):
        for i, name in enumerate(self.game.items[self.target]):
            btn = discord.ui.Button(label=name, style=discord.ButtonStyle.success)
            btn.callback = self.create_steal_callback(i, name)
            self.add_item(btn)
        
        cancel = discord.ui.Button(label="뒤로가기", style=discord.ButtonStyle.secondary)
        cancel.callback = self.back_callback
        self.add_item(cancel)

    def create_steal_callback(self, item_idx, item_name):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.game.current_player: return
            
            # 아드레날린 카드와 상대방 아이템을 가방에서 먼저 소모(pop) 처리합니다.
            if self.adrenaline_idx is not None:
                self.game.items[interaction.user].pop(self.adrenaline_idx)
            
            self.game.items[self.target].pop(item_idx)
            user = interaction.user
            u_name = clean_name(user)
            t_name = clean_name(self.target)
            
            if '🔍' in item_name:
                await interaction.response.send_message(f"🔍 [아드레날린] 현재 장전된 탄환은 **{self.game.shells[0]}**입니다.", ephemeral=True)
                await self.parent_view.main_message.edit(embed=self.parent_view.create_embed(f"💉 **{u_name}**님이 **{t_name}**님의 돋보기를 훔쳐 사용했습니다."), view=self.parent_view)
                return
            elif '🚬' in item_name:
                self.game.hp[user] = min(self.game.max_hp, self.game.hp[user] + 1)
                await self.parent_view.update_game_state(interaction, f"💉 **{u_name}**님이 **{t_name}**님의 담배를 훔쳐 체력을 회복했습니다.")
            elif '🪚' in item_name:
                self.game.dmg = 2
                await self.parent_view.update_game_state(interaction, f"💉 **{u_name}**님이 **{t_name}**님의 톱을 훔쳐 총구를 잘랐습니다!")
            elif '⛓️‍💥' in item_name:
                targets = [p for p in self.game.alive_players if p != user]
                if len(targets) == 1:
                    if targets[0] not in self.game.skip_list: self.game.skip_list.append(targets[0])
                    await self.parent_view.update_game_state(interaction, f"💉 **{u_name}**님이 **{t_name}**님의 수갑을 훔쳐 **{clean_name(targets[0])}**님에게 채웠습니다.")
                else:
                    # 3인 이상 게임 시 타겟을 다시 선택해야 하므로, TargetSelectView로 전환하되 상호작용 실패를 방지합니다.
                    await interaction.response.edit_message(view=TargetSelectView(self.game, self.parent_view, "adrenaline_handcuff", extra_info=t_name))
            elif '💊' in item_name:
                p_died = False
                if random.choice([True, False]):
                    self.game.hp[user] = min(self.game.max_hp, self.game.hp[user] + 2)
                    res = f"💉 **{u_name}**님이 **{t_name}**님의 상한 약을 훔쳐 먹었습니다!\n🤩 **대성공:** 체력을 2칸 회복합니다!"
                else:
                    self.game.hp[user] -= 1
                    res = f"💉 **{u_name}**님이 **{t_name}**님의 상한 약을 훔쳐 먹었습니다!\n🤢 **부작용:** 체력을 1칸 잃었습니다."
                    if self.game.hp[user] <= 0:
                        self.game.alive_players.remove(user)
                        p_died = True
                        self.game.next_turn(current_player_removed=True)
                await self.parent_view.update_game_state(interaction, res)
            elif '🎛️' in item_name:
                current_shell = self.game.shells[0]
                self.game.shells[0] = '⚪ 공포탄' if current_shell == '🔴 실탄' else '🔴 실탄'
                await self.parent_view.update_game_state(interaction, f"💉 **{u_name}**님이 **{t_name}**님의 변환기를 훔쳐 약실 탄환을 반전시켰습니다!")
            elif '🎮' in item_name:
                self.game.direction *= -1
                await self.parent_view.update_game_state(interaction, f"💉 **{u_name}**님이 **{t_name}**님의 리모컨을 훔쳐 사용했습니다! 턴 진행 방향이 반대로 바뀝니다.")
            elif '💉' in item_name:
                # 아드레날린으로 아드레날린을 훔친 특이 케이스 -> 다시 대상 선택으로 이동
                await interaction.response.edit_message(view=AdrenalineTargetView(self.game, self.parent_view, adrenaline_idx=None))
                
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player: return
        await interaction.response.edit_message(view=AdrenalineTargetView(self.game, self.parent_view, self.adrenaline_idx))

# --- [봇 시작 명령어] ---
@bot.tree.command(name="벅샷", description="게임을 진행합니다")
async def buckshot(interaction: discord.Interaction, 상대1: discord.Member, 상대2: discord.Member = None, 상대3: discord.Member = None):
    players = [interaction.user]
    for p in [상대1, 상대2, 상대3]:
        if p and p not in players and not p.bot: 
            players.append(p)
    if len(players) < 2: 
        return await interaction.response.send_message("❌ 게임에 참여할 인원이 부족합니다.", ephemeral=True)
    
    game = BuckshotGame(players)
    view = BuckshotView(game)
    await interaction.response.send_message(embed=view.create_embed("🎮 게임 시작!"), view=view)
    view.main_message = await interaction.original_response()

import time # 맨 위에 import 하거나, 여기에 추가하세요

# 기존의 keep_alive() 호출 및 time.sleep 코드 삭제
# @bot.event on_ready 아래에 있는 토큰 실행 부분만 남깁니다.

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ {bot.user.name} 룰렛 온라인')

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    bot.run(TOKEN)
