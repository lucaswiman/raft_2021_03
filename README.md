# Rafting Trip - March 22-26, 2021

Hello! This is the course project repo for the "Rafting Trip"
course.  This project will serve as the central point of discussion, code
sharing, debugging, and other matters related to the project.

Although each person will work on their own code, it is requested
that all participants work from this central repo. First, create a
a branch for yourself:

    bash % git clone https://github.com/dabeaz-course/raft_2021_03
    bash % cd raft_2021_03
    bash % git checkout -b yourname
    bash % git push -u origin yourname

Do all of your subsequent work in your branch of this central repository. 

The use of GitHub makes it easier for me to look at your code and
answer questions (you can point me at your code, raise an issue,
etc.).  It also makes it easier for everyone else to look at your code
and to get ideas.  Implementing Raft is hard. Everyone is going to
have different ideas about the implementation, testing, and other
matters.  By having all of the code in one place, it will be better
and more of a shared experience.

I will also be using the repo to commit materials, solutions, and 
other things as the course date nears and during the course itself.

Finally, the repo serves as a good record for everything that happened
during the course after the fact.  

Cheers,
Dave

## Live Session

The course is conducted live from 09:30 to 17:30 US Central Daylight Time
(UTC-05:00).  Here are details about the Zoom meeting:

Topic: Rafting Trip

Join Zoom Meeting
https://us02web.zoom.us/j/84678466137?pwd=VVFkaE13U3doZ2swWll1ZjR1UWJpdz09

Meeting ID: 846 7846 6137
Passcode: 886054

I will be in the meeting approximately 30 minutes prior to the start
time if you need to test your set up.

Presentation slides are available in the [Raft.pdf](Raft.pdf) file.

## Live Chat

For live chat during the course, we use Gitter.  Here is a link:

* [https://gitter.im/dabeaz-course/raft_2021_03](https://gitter.im/dabeaz-course/raft_2021_03)

## Raft Resources

Our primary source of information on Raft is found at https://raft.github.io.
You should also watch the video at https://www.youtube.com/watch?v=YbZ3zDzDnrw.  Of
particular interest is the [Raft Paper](https://raft.github.io/raft.pdf).

## The Challenge of Raft

One of the biggest challenges in the Raft project is knowing precisely
where to start.  As you read the Raft paper, you should be thinking
about "where would I actually start with an implementation?"  There
are different facets that need to be addressed.  For example, at one
level, there's a networking layer involving machines and
messages. Maybe this is the starting point (at the low level).
However, there's also the "logic" of Raft (e.g., leader election
with leaders, followers, and candidates). So, an alternative might be to
approach from a high level instead.  And then there are applications
that might utilize Raft such as a key-value store database. Do you
build that first and then expand Raft on top of it?

The other challenge concerns testing and debugging.  How do you
implement it while having something that you can actually test and
verify?

## Introductory Video

* [Course Setup](https://vimeo.com/401115908/a81c795591) (2 mins)

## Live Session Videos

Video from the live session will be posted here.

**Day 1**

* [Course Introduction](https://vimeo.com/527558814/996aec5e93) (74 min)
* [Project 1](https://vimeo.com/527559442/f8c436174e) (29 min)
* [Project 1/2](https://vimeo.com/527559690/805219b471) (5 min)
* [Project 2](https://vimeo.com/527559780/db306adf1e) (21 min)
* [Project 2](https://vimeo.com/527559974/17e5af8a95) (21 min)
* [Project 2](https://vimeo.com/527560154/d66b828452) (9 min)

**Day 2**

* [Project 3](https://vimeo.com/528078169/3bbc8833ab) (21 min)
* [TLA+/Project 4](https://vimeo.com/528078345/554cf766f5) (60 min)
* [Project 4](https://vimeo.com/528078814/b36de25e98) (23 min)
* [Project 4/5](https://vimeo.com/528078969/c92770353d) (30 min)
* [Project 5/6](https://vimeo.com/528079223/f1cb61b29d) (30 min)

**Day 3**

* [Project 6](https://vimeo.com/528592247/85bf2434a3) (42 min)
* [Project 6](https://vimeo.com/528592576/6cb15a5c01) (14 min)
* [Project 7](https://vimeo.com/528592705/4f5cf3d943) (30 min)
* [Project 7](https://vimeo.com/528592919/b9a9c75fb7) (37 min)

**Day 4**

* [Project 8](https://vimeo.com/529135662/c450db6aa3) (53 min)
* [Project 8](https://vimeo.com/529135999/a9923db521) (31 min)
* [Project 9](https://vimeo.com/529136197/9ce9bae29e) (36 min)
* [Project 9](https://vimeo.com/529136428/aeb3718271) (20 min)

## Preparation Exercises

The following project covers some background material related to socket
programming and concurrency that might help with the course:

* [Warmup Project](docs/Warmup.md)

The Raft project is similar to what might be taught in a graduate
distributed systems course such as MIT 6.824. A lot of information is
available on the course
[website](https://pdos.csail.mit.edu/6.824/index.html).

## Project Milestones

The following projects guide you through one possible path for implementing Raft.
This is not necessarily the only way to do it.  However, it's an approach
that has often worked in the past.

* [Project 1 - Foundations](docs/Project1_Foundations.md)
* [Project 2 - Model Building](docs/Project2_ModelBuilding.md)
* [Project 3 - Simulation](docs/Project3_Simulation.md)
* [Project 4 - The Log](docs/Project4_TheLog.md)
* [Project 5 - Raft Network](docs/Project5_RaftNet.md)
* [Project 6 - Log Replication](docs/Project6_LogReplication.md)
* [Project 7 - Consensus](docs/Project7_Consensus.md)
* [Project 8 - Leader Election](docs/Project8_LeaderElection.md)
* [Project 9 - Timing](docs/Project9_Timing.md)
* [Project 10 - The System](docs/Project10_System.md)
* [Project 11 - The Rest of Raft](docs/Project11_Everything.md)

## Interesting Resources

* [Concurrency: the Works of Leslie Lamport](docs/documents/3335772.pdf) (PDF)
* [Implementing Raft, Eli Bendersky](https://eli.thegreenplace.net/2020/implementing-raft-part-0-introduction/) (blog)
* [Notes on Raft, Chelsea Troy](https://chelseatroy.com/tag/raft/) (blog)
* [A Recent Raft-Related Failure](https://blog.cloudflare.com/a-byzantine-failure-in-the-real-world/)
* [The Google Outage of Dec 14](https://status.cloud.google.com/incident/zall/20013#20013004)

