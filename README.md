# walker_with_clean_design

simply type: python run.py

The TestCommunity inherits of MultiChainCommunity, so it has all Messages and Conversion Defined in MultiChainCommunity.

all functions relevant to walkers are listed in it.(take_step(),create_introduction_request() etc.), it is almost the same with original walker in Community base class. 

If there are something wrong with dispersy and Tribler in "com" folder, just put your own dispersy and tribler.Tribler there.

