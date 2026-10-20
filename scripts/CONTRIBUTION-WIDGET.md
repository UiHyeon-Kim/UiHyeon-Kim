# Contribution widget

The 3D contribution widget refreshes daily at 00:23 UTC (09:23 Asia/Seoul),
and can be refreshed manually from the `Refresh contribution widget` workflow.
The workflow fetches the latest 365 days of the account's anonymous public
GitHub contribution calendar, validates every observed date, renders the widget,
and commits only the SVG and its data file after the tests pass.

No personal access token is used. The workflow uses the repository's temporary
`GITHUB_TOKEN` to commit the refreshed output. Streak remains connected to its
existing service endpoint in the profile README.

The normal-mode calendar geometry in `render_contribution_calendar.py` is
derived from [github-profile-3d-contrib](https://github.com/yoshi389111/github-profile-3d-contrib)
at commit `e235d118909be71eb7edb05482a3de4e76156df3`. Its MIT license is retained
in `third_party/github-profile-3d-contrib-LICENSE`. The Python port uses anonymous
public-calendar HTML, omits the language and radar panels, and applies the
existing blue-gray palette and 900 by 414 frame.
