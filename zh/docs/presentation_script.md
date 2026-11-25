# Presentation 讲稿（5 分钟版，对应 pptx）

对应文件：`PlanB_Proposal_Presentation.pptx`（正文 8 页，第 9 页起是附录）。

老师给每人 4 到 5 分钟。照下面讲大概 4 分 15 秒，留一点余量。观众主要是华语同学，所以英文都用简单的词和短句，意思对就行，不用一字不差。

每页三块：先是一句"记住这句"，记住它就不会卡住；然后是中文意思，帮你理解；最后是英文怎么说，正式讲时照着说。pptx 里每页的演讲者备注就是这里的英文。

整个故事连起来就是：能做三件事 → 大模型也算错钱 → 所以分工 → 演示 1150 → 我们怎么测 → 结果 → 语言给 LLM，规则和钱给代码，决定给用户。

---

## 第 1 页　封面（10 秒）

记住这句：LLM 负责理解，代码负责检查和算钱，用户做决定。

中文意思：大家好，我是 Zhang Yupeng。我的项目叫 PlanB，是一个 AI 旅行助手。思路很简单：LLM 负责理解，代码负责检查和算钱，最后由用户做决定。

英文这样说：
> Hi everyone, I'm Zhang Yupeng. My project is PlanB, an AI travel helper.
> The idea is simple: the LLM understands, the code checks and counts, and the user decides.

---

## 第 2 页　What PlanB does（40 秒）

记住这句：一段话出行程，聊天改行程，出状况就重新规划。

中文意思：PlanB 能做三件事。第一，你用一段话写下旅行：日期、想去的地方、喜欢什么、已经订了什么。PlanB 给你排好每天的行程，订好的东西不会动。第二，你可以直接聊天改行程，比如说"我不想去浅草寺了"，它会给你几个选项挑。第三，旅途中出了状况，比如下雨或者想多待一天，它只改受影响的部分，还告诉你要多花多少钱。

英文这样说：
> PlanB does three things.
> First, you write your trip in one paragraph: the dates, the places you want to see, what you like, and what you have booked. PlanB makes a daily plan and keeps your bookings fixed.
> Second, you can change the plan by chat. For example: "I don't want to go to Senso-ji." PlanB gives you some options to pick from.
> Third, if something changes during the trip, like rain or staying one more day, PlanB changes only what is affected and tells you the extra cost.

---

## 第 3 页　Even a 550B model gets the price wrong（35 秒）

记住这句：大模型漏了 200 块改签费，说 950，其实是 1150。

中文意思：那为什么不直接让 LLM 来做？我们试过。我们让一个 5500 亿参数的大模型处理"多待一天"，它找对了受影响的订单，回答看起来也不错，但是漏掉了 200 块的改签费。它说要多付 950，正确答案是 1150。小模型更糟，会把订好的晚餐挪走，甚至整天重排。

英文这样说：
> Why not just ask an LLM to do all this? We tried.
> We asked a very large model, with 550 billion parameters, to add one more day to the trip. It found the right bookings, and the answer looks good.
> But it forgot the 200-yuan change fee. It said 950 yuan. The right answer is 1,150.
> Small models are even worse. They move booked dinners and change whole days.

---

## 第 4 页　How PlanB splits the work（35 秒）

记住这句：LLM 只负责听懂，难的部分交给代码。

中文意思：所以 PlanB 把工作分开。LLM 只负责听懂用户的请求。难的部分交给普通代码：检查规则，比如营业时间和路上要花的时间；只改受影响的地方；再按订单规则把钱算出来。不知道的就说不知道，不会当成 0。最后 LLM 把结果解释一遍，用户说行还是不行。

英文这样说：
> So PlanB splits the work.
> The LLM only understands the request.
> Then normal code does the hard part. It checks the rules, like opening hours and travel time, changes only what is affected, and counts the money from the booking rules. If something is unknown, it says unknown, not zero.
> At the end, the LLM explains the result, and the user says yes or no.

讲的时候可以用手指着图，从左上角顺着箭头绕一圈。

---

## 第 5 页　Demo: stay one more day（30 秒）

记住这句：200 加 350 加 600，等于 1150。

中文意思：这是同一个请求在 PlanB 里的结果。只有返程机票和酒店受影响。费用是 200 改签费，加 350 差价，加 600 多住一晚，一共 1150，每个数字都来自订单规则。PlanB 不会自己去订票，最后还是用户决定。

英文这样说：
> Here is the same request in PlanB.
> Only the return flight and the hotel are affected.
> The cost is 200 plus 350 plus 600, so 1,150 yuan. Every number comes from a booking rule.
> PlanB does not book anything by itself. The user still decides.

---

## 第 6 页　How we test（45 秒）

记住这句：两组手写的测试、四种方法、两个模型、全对才算对。

中文意思：那我们是怎么测的？我们手写了两组测试。第一组 10 个，是旅途中出状况，比如下雨、延误。第二组 13 个，是新建行程和聊天修改。我们比较四种方法：两种是让 LLM 全包，一种只给普通提示，一种给一长串规则；然后是 PlanB；还有给 PlanB 正确请求的版本，用来看错误是不是出在读懂请求这一步。我们用了两个免费模型，一小一大。一个案例要每一项都对，包括钱，才算做对。

英文这样说：
> So how did we test it?
> We wrote two test sets by hand. The first has 10 cases where something changes during the trip, like rain or a delay. The second has 13 cases where you plan a trip or change it by chat.
> We compare four methods. Two of them let the LLM do everything: one with a simple prompt, and one with a long list of rules. Then PlanB. And PlanB with the correct request, which shows us if errors come from reading the request.
> We use two free models, a small one and a large one.
> A case counts as solved only if everything is right, including the money.

讲的时候按"左上、右上、左下、右下"的顺序指，正好就是这四句。

---

## 第 7 页　Results: number of cases solved（40 秒）

记住这句：小模型下 PlanB 23 个对 14 个，大模型下别人算错钱，读对了就 23 个全对。

中文意思：结果是这样的。用小模型时，两种让 LLM 全包的方法几乎全错，PlanB 还能做对 23 个里的 14 个。用大模型时，LLM 全包的方法行程排得不错，但钱还是算错。PlanB 的错误都出在小模型读长请求上，给它正确的请求时，23 个全对。而且它用的 token 少 5 到 8 倍。

英文这样说：
> Here are the results.
> With the small model, the two LLM methods solve almost nothing, but PlanB still solves 14 of the 23 cases.
> With the large model, the LLM methods plan well, but they still get the money wrong.
> PlanB's mistakes all come from reading long requests with the small model. When it gets the correct request, it solves all 23 cases.
> It also uses five to eight times fewer tokens.

讲的时候可以先指表格里加粗的 PlanB 那一行，再指最后一行。

---

## 第 8 页　Summary（20 秒）

记住这句：语言给 LLM，规则和钱给代码，决定给用户。

中文意思：我想说的就是：语言交给 LLM，规则和钱交给代码，决定交给用户。现在是 23 个我自己写的案例上的初步结果，接下来会加更多测试。谢谢大家！

英文这样说：
> So my main message: let the LLM handle language, let code handle rules and money, and let the user decide.
> These are early results on 23 cases that I wrote myself, so next I will add more test cases.
> Thank you!

---

## 答疑小抄

被问到时先用一句话回答，需要的话再翻到对应的附录页。

**问：评测是不是偏向你自己的方法？**
标准答案是我按订单规则手写的，不是 PlanB 算出来的；所有方法用同一个检查器打分，"LLM + rules"还多给了一份规则。
> I wrote the right answers by hand from the booking rules, and the same checker scores every method. The "LLM + rules" method even gets an extra list of rules.

**问：大模型已经很接近了，为什么还要 PlanB？**
大模型还是会算错钱，用的 token 是 PlanB 的 5 到 8 倍。PlanB 的结果是代码检查过的，小模型也能用。
> The large model still gets the money wrong, and it uses five to eight times more tokens. PlanB's answers are checked by code, and it also works with a small model.

**问：为什么小模型新建行程只有 2/8？**
小模型读长段落会漏东西，最常见的是漏掉返程航班。读对的时候是 8/8。所以 PlanB 会先把理解的内容给用户确认。
> The small model misses things in long paragraphs, usually the return flight. When the request is read correctly, it's 8 out of 8. That's why PlanB shows the user what it understood first.

**问：规划都是代码做的，这还算 AI 项目吗？**
算。LLM 负责所有理解语言的部分，我研究的就是哪些事该交给 LLM、哪些该交给代码，实验比的也是 LLM 的不同用法。
> Yes. The LLM handles all the language. My question is which jobs should go to the LLM and which to code, and the tests compare different ways of using LLMs.

**问：为什么选这两个模型？**
没有预算，只用免费开源模型。小模型是在 CPU 上跑的 Qwen2.5-3B，大模型是当时能免费用的最大的开源模型。换模型只要改设置。
> I had no budget, so I used free open models. The small one is Qwen 2.5 3B running on a CPU, and the large one was the biggest free open model I could use. Changing the model is just a setting.

**问：价格和交通是真的吗？**
不是，都是模拟数据，而且标清楚了。PlanB 不订票、不付款，也不查实时价格。
> No, it's simulated data, and it's marked as simulated. PlanB never books, pays or checks live prices.

**问：接下来做什么？**
扩到大约 40 个案例，留一部分只用来测试；做消融实验，也就是拿掉某个部分看影响；再加一个中等大小的模型。
> I'll grow to about 40 cases and keep some only for testing. I'll also remove parts of PlanB one by one to see what matters, and add a mid-size model.
